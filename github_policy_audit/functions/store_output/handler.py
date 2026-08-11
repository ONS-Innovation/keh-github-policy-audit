"""Lambda handler to store check results to S3."""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

from utils.scorecard import calculate_repository_rating
from utils.scorecard import load_scorecard_criteria
from utils.scorecard import serialise_scorecard_criteria
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _normalise_environment(raw_environment: str | None) -> str:
    """Normalise supported environments."""
    environment = (raw_environment or "local").lower()
    if environment in {"local", "prod"}:
        return environment
    raise ValueError("ENVIRONMENT must be either 'local' or 'prod'")


def _is_pass(check_output):
    """Return True when a check result reports a passing result."""
    return (
        isinstance(check_output, dict)
        and str(check_output.get("result", "")).lower() == "pass"
    )


def _calculate_entity_compliance(entity_checks: dict) -> bool:
    """Return compliance derived from all check outputs.

    Compliance is always calculated in this function from check results.
    """
    return all(
        _is_pass(check_output)
        for check_name, check_output in entity_checks.items()
        if check_name != "is_compliant"
    )


def _normalise_repository_entry(repository_data) -> dict[str, dict | bool]:
    """Return repository entry with nested checks and computed compliance."""
    if not isinstance(repository_data, dict):
        return {"checks": {}, "is_compliant": False}

    checks_source = repository_data.get("checks")
    if not isinstance(checks_source, dict):
        checks_source = repository_data

    checks = {
        check_name: {k: v for k, v in check_output.items() if k != "check_name"}
        if isinstance(check_output, dict)
        else check_output
        for check_name, check_output in checks_source.items()
        if check_name not in {"is_compliant", "rating"}
    }

    return {
        "checks": checks,
        "is_compliant": _calculate_entity_compliance(checks),
    }


def _normalise_organisation_checks(
    organisation_checks, organisation_results
) -> dict[str, dict]:
    """Return organisation checks as a dictionary keyed by check name."""
    if isinstance(organisation_checks, dict):
        return organisation_checks
    if organisation_checks is not None:
        raise ValueError("'organisation_checks' must be a dictionary")

    if not isinstance(organisation_results, list):
        return {}

    checks: dict[str, dict] = {}
    for result in organisation_results:
        if not isinstance(result, dict):
            continue
        check_name = result.get("check_name")
        if isinstance(check_name, str) and check_name:
            checks[check_name] = {k: v for k, v in result.items() if k != "check_name"}
    return checks


def _normalise_repository_checks(repositories, repository_results) -> dict[str, dict]:
    """Return repositories keyed by name with nested check results."""
    if isinstance(repositories, dict):
        return {
            repository_name: _normalise_repository_entry(repository_checks)
            for repository_name, repository_checks in repositories.items()
        }
    if repositories is not None:
        raise ValueError("'repositories' must be a dictionary keyed by repository name")

    if not isinstance(repository_results, list):
        return {}

    repository_checks: dict[str, dict] = {}
    for repository_result in repository_results:
        if not isinstance(repository_result, dict):
            continue

        repository_name = repository_result.get("repository_name")
        if not isinstance(repository_name, str) or not repository_name:
            continue

        checks_by_name: dict[str, dict] = {}
        for check_result in repository_result.get("checks", []):
            if not isinstance(check_result, dict):
                continue
            check_name = check_result.get("check_name")
            if isinstance(check_name, str) and check_name:
                checks_by_name[check_name] = check_result

        repository_checks[repository_name] = _normalise_repository_entry(
            {"checks": checks_by_name}
        )

    return repository_checks


def _load_repository_checks_from_s3(
    *,
    s3_client,
    bucket_name: str,
    owner: str,
    run_id: str,
) -> dict[str, dict]:
    """Load per-repository results from S3 and return keyed repository checks.

    Flow:
    1. List all JSON objects for the run prefix.
    2. Iterate object keys.
    3. Read each object body.
    4. Normalise checks payload and build repository map.
    """
    prefix = f"audit-runs/{owner}/{run_id}/repositories/"
    repository_checks: dict[str, dict] = {}
    repository_keys: list[str] = []

    paginator = s3_client.get_paginator("list_objects_v2")
    for response in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in response.get("Contents", []):
            key = obj.get("Key")
            if isinstance(key, str) and key.endswith(".json"):
                repository_keys.append(key)

    for key in repository_keys:
        raw_body = s3_client.get_object(Bucket=bucket_name, Key=key)["Body"].read()
        payload = json.loads(raw_body)
        if not isinstance(payload, dict):
            continue

        # Prefer explicit field, fallback to filename for resilience.
        repository_name = payload.get("repository_name")
        if not isinstance(repository_name, str) or not repository_name:
            repository_name = key.rsplit("/", 1)[-1].removesuffix(".json")
        if not repository_name:
            continue

        checks_payload = payload.get("checks")
        if isinstance(checks_payload, dict):
            repository_checks[repository_name] = _normalise_repository_entry(
                {"checks": checks_payload}
            )
        else:
            repository_checks[repository_name] = {"checks": {}, "is_compliant": False}

    return repository_checks


def _normalise_team_checks(teams, team_results) -> dict[str, dict]:
    """Return teams keyed by slug or name with nested check results."""
    if isinstance(teams, dict):
        return {
            team_name: _normalise_repository_entry(team_checks)
            for team_name, team_checks in teams.items()
        }
    if teams is None:
        return {}

    if not isinstance(teams, list):
        raise ValueError(
            "'teams' must be a dictionary, or a list when 'team_results' is provided"
        )
    if not isinstance(team_results, list):
        raise ValueError(
            "'team_results' must be provided as a list when 'teams' is a list"
        )

    checks_by_team: dict[str, dict] = {}
    for index, team_result in enumerate(team_results):
        if not isinstance(team_result, dict):
            continue

        team = (
            teams[index]
            if index < len(teams) and isinstance(teams[index], dict)
            else {}
        )
        team_key = team.get("slug") or team.get("name") or f"team-{index}"

        check_name = team_result.get("check_name")
        if not isinstance(check_name, str) or not check_name:
            continue

        checks_by_team.setdefault(team_key, {})[check_name] = {
            k: v for k, v in team_result.items() if k != "check_name"
        }

    for team_key, team_checks in list(checks_by_team.items()):
        checks_by_team[team_key] = _normalise_repository_entry({"checks": team_checks})

    return checks_by_team


def handler(event, context):
    """Store output from either canonical maps or raw Step Function map/parallel arrays."""
    log_info(logger, "lambda_invoked", event_keys=sorted(event.keys()))

    owner = event["owner"]

    environment = _normalise_environment(os.environ.get("ENVIRONMENT", "local"))
    s3_client = boto3.client("s3") if environment == "prod" else None

    bucket_name = event.get("output_bucket") or os.environ.get("S3_BUCKET_NAME")
    run_id = event.get("run_id")
    rate_limit_start = event.get("rate_limit_start")
    rate_limit_end = event.get("rate_limit_end")

    repositories = _normalise_repository_checks(
        event.get("repositories"), event.get("repository_results")
    )
    if not repositories and isinstance(run_id, str) and run_id:
        if environment == "prod":
            if not bucket_name:
                raise ValueError(
                    "output_bucket (or S3_BUCKET_NAME) is required in prod when using run_id"
                )
            repositories = _load_repository_checks_from_s3(
                s3_client=s3_client,
                bucket_name=bucket_name,
                owner=owner,
                run_id=run_id,
            )

    # Load scorecard criteria

    scorecard_ratings = load_scorecard_criteria(
        environment=environment,
        bucket_name=bucket_name,
        s3_client=s3_client,
    )

    # Calculate repository ratings and tally scorecard status counts

    scorecard_status_counts = {rating["name"]: 0 for rating in scorecard_ratings}
    scorecard_status_counts["unrated"] = 0

    for repository_name, repository_checks in repositories.items():
        if not isinstance(repository_checks, dict):
            continue
        checks = repository_checks.get("checks")
        if not isinstance(checks, dict):
            checks = {}
        rating = calculate_repository_rating(checks, scorecard_ratings)
        repositories[repository_name]["rating"] = rating
        scorecard_status_counts[rating] = scorecard_status_counts.get(rating, 0) + 1

    teams = _normalise_team_checks(event.get("teams"), event.get("team_results"))
    organisation_checks = _normalise_organisation_checks(
        event.get("organisation_checks"), event.get("organisation_results")
    )

    now = datetime.now(timezone.utc)

    summary = {
        "total_repositories": len(repositories),
        "compliant_repositories": sum(
            1
            for repo_checks in repositories.values()
            if isinstance(repo_checks, dict) and repo_checks.get("is_compliant") is True
        ),
        "total_teams": len(teams),
        "compliant_teams": sum(
            1
            for team_checks in teams.values()
            if isinstance(team_checks, dict) and team_checks.get("is_compliant") is True
        ),
        "repository_checks": {},
        "organisation_checks": {},
        "team_checks": {},
        "repository_ratings": scorecard_status_counts,
    }

    for _, repository_entry in repositories.items():
        if not isinstance(repository_entry, dict):
            continue
        checks = repository_entry.get("checks", {})
        if not isinstance(checks, dict):
            continue
        for check_name, check_output in checks.items():
            if check_name not in summary["repository_checks"]:
                summary["repository_checks"][check_name] = {"total": 0, "compliant": 0}
            summary["repository_checks"][check_name]["total"] += 1
            if _is_pass(check_output):
                summary["repository_checks"][check_name]["compliant"] += 1

    for check_name, check_output in organisation_checks.items():
        summary["organisation_checks"][check_name] = {
            "compliant": _is_pass(check_output)
        }

    for _, team_entry in teams.items():
        for check_name, check_output in team_entry.get("checks", {}).items():
            if check_name not in summary["team_checks"]:
                summary["team_checks"][check_name] = {"total": 0, "compliant": 0}
            summary["team_checks"][check_name]["total"] += 1
            if _is_pass(check_output):
                summary["team_checks"][check_name]["compliant"] += 1

    output = {
        "owner": owner,
        "repositories": repositories,
        "scorecard_criteria": serialise_scorecard_criteria(scorecard_ratings),
        "organisation_checks": organisation_checks,
        "teams": teams,
        "summary": summary,
        "rate-limit-start": rate_limit_start,
        "rate-limit-end": rate_limit_end,
        "timestamp": now.isoformat(),
    }

    result_file_suffix = (
        run_id
        if isinstance(run_id, str) and run_id
        else now.strftime("%Y-%m-%d/%H-%M-%S")
    )
    key = f"audit-results/{owner}/{result_file_suffix}.json"
    local_output_path = None

    if environment == "prod":
        if not bucket_name:
            raise ValueError(
                "output_bucket (or S3_BUCKET_NAME) environment variable not set"
            )

        log_info(logger, "storing_results", storage="s3", bucket=bucket_name, key=key)
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(output, indent=2),
            ContentType="application/json",
        )
    else:
        bucket_name = None
        output_dir = os.path.join("outputs", owner)
        os.makedirs(output_dir, exist_ok=True)
        local_output_path = os.path.join(
            output_dir, f"{now.strftime('%Y-%m-%d_%H-%M-%S')}.json"
        )

        with open(local_output_path, "w", encoding="utf-8") as file:
            json.dump(output, file, indent=2)

        log_info(
            logger,
            "stored_results",
            environment="local",
            local_output_path=local_output_path,
        )

    log_info(
        logger,
        "lambda_completed",
        owner=owner,
        repositories_count=len(repositories),
        organisation_checks_count=len(organisation_checks),
        teams_count=len(teams),
    )

    return {
        "status": "success",
        "environment": environment,
        "bucket": bucket_name,
        "key": key,
        "local_output_path": local_output_path,
        "owner": owner,
        "run_id": run_id,
        "rate-limit-start": rate_limit_start,
        "rate-limit-end": rate_limit_end,
    }
