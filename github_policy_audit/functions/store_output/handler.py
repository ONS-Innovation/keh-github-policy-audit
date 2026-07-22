"""Lambda handler to store check results to S3."""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


def _normalise_checks_with_compliance(entity_checks) -> dict:
    """Return checks dictionary with a computed is_compliant field."""
    if not isinstance(entity_checks, dict):
        return {"is_compliant": False}

    normalised = {
        check_name: check_output
        for check_name, check_output in entity_checks.items()
        if check_name != "is_compliant"
    }
    normalised["is_compliant"] = _calculate_entity_compliance(normalised)
    return normalised


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
            checks[check_name] = result
    return checks


def _normalise_repository_checks(repositories, repository_results) -> dict[str, dict]:
    """Return repository checks as {repository_name: {check_name: check_output}}."""
    if isinstance(repositories, dict):
        return {
            repository_name: _normalise_checks_with_compliance(repository_checks)
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

        repository_checks[repository_name] = _normalise_checks_with_compliance(
            checks_by_name
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
            repository_checks[repository_name] = _normalise_checks_with_compliance(
                checks_payload
            )
        else:
            repository_checks[repository_name] = {"is_compliant": False}

    return repository_checks


def _normalise_team_checks(teams, team_results) -> dict[str, dict]:
    """Return team checks as {team_slug_or_name: {check_name: check_output}}."""
    if isinstance(teams, dict):
        return {
            team_name: _normalise_checks_with_compliance(team_checks)
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

        checks_by_team.setdefault(team_key, {})[check_name] = team_result

    for team_key, team_checks in list(checks_by_team.items()):
        checks_by_team[team_key] = _normalise_checks_with_compliance(team_checks)

    return checks_by_team


def handler(event, context):
    """Store output from either canonical maps or raw Step Function map/parallel arrays."""
    log_info(logger, "lambda_invoked", event_keys=sorted(event.keys()))

    owner = event["owner"]

    environment = os.environ.get("ENVIRONMENT", "local").lower()
    if environment not in {"local", "prod"}:
        raise ValueError("ENVIRONMENT must be either 'local' or 'prod'")

    bucket_name = event.get("output_bucket") or os.environ.get("S3_BUCKET_NAME")
    run_id = event.get("run_id")

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
                s3_client=boto3.client("s3"),
                bucket_name=bucket_name,
                owner=owner,
                run_id=run_id,
            )
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
    }

    for _, checks in repositories.items():
        for check_name, check_output in checks.items():
            if check_name == "is_compliant":
                continue
            if check_name not in summary["repository_checks"]:
                summary["repository_checks"][check_name] = {"total": 0, "compliant": 0}
            summary["repository_checks"][check_name]["total"] += 1
            if _is_pass(check_output):
                summary["repository_checks"][check_name]["compliant"] += 1

    for check_name, check_output in organisation_checks.items():
        summary["organisation_checks"][check_name] = {
            "compliant": _is_pass(check_output)
        }

    output = {
        "owner": owner,
        "repositories": repositories,
        "organisation_checks": organisation_checks,
        "teams": teams,
        "summary": summary,
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
        boto3.client("s3").put_object(
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
    }
