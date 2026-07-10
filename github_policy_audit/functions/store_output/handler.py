"""Lambda handler to store check results to S3."""

import json
import logging
import os
from datetime import datetime, timezone

import boto3


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _is_pass(check_output):
    """Return True when a check result reports a passing status."""
    return (
        isinstance(check_output, dict)
        and str(check_output.get("status", "")).lower() == "pass"
    )


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
        return repositories
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

        repository_checks[repository_name] = checks_by_name

    return repository_checks


def _normalise_team_checks(teams, team_results) -> dict[str, dict]:
    """Return team checks as {team_slug_or_name: {check_name: check_output}}."""
    if isinstance(teams, dict):
        return teams
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

        checks_by_team[team_key] = {check_name: team_result}

    return checks_by_team


def handler(event, context):
    """Store output from either canonical maps or raw Step Function map/parallel arrays."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")

    owner = event.get("owner")
    if not owner:
        raise ValueError("Event must include non-empty 'owner'")

    repositories = _normalise_repository_checks(
        event.get("repositories"), event.get("repository_results")
    )
    teams = _normalise_team_checks(event.get("teams"), event.get("team_results"))
    organisation_checks = _normalise_organisation_checks(
        event.get("organisation_checks"), event.get("organisation_results")
    )

    environment = os.environ.get("ENVIRONMENT", "local").lower()
    if environment not in {"local", "prod"}:
        raise ValueError("ENVIRONMENT must be either 'local' or 'prod'")

    now = datetime.now(timezone.utc)

    summary = {
        "total_repositories": len(repositories),
        "compliant_repositories": sum(
            1
            for repo_checks in repositories.values()
            if isinstance(repo_checks, dict)
            and all(_is_pass(check) for check in repo_checks.values())
        ),
        "total_teams": len(teams),
        "compliant_teams": sum(
            1
            for team_checks in teams.values()
            if isinstance(team_checks, dict)
            and all(_is_pass(check) for check in team_checks.values())
        ),
        "repository_checks": {},
        "organisation_checks": {},
    }

    for _, checks in repositories.items():
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

    output = {
        "owner": owner,
        "repositories": repositories,
        "organisation_checks": organisation_checks,
        "teams": teams,
        "summary": summary,
        "timestamp": now.isoformat(),
    }

    key = f"audit-results/{owner}/{now.strftime('%Y-%m-%d/%H-%M-%S')}.json"
    local_output_path = None

    if environment == "prod":
        bucket_name = os.environ.get("S3_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable not set")

        logger.info(f"Storing results to s3://{bucket_name}/{key}")
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

        logger.info(f"ENVIRONMENT=local, wrote output to {local_output_path}")

    logger.info(
        f"Lambda completed owner={owner} repositories_count={len(repositories)} "
        f"organisation_checks_count={len(organisation_checks)} "
        f"teams_count={len(teams)}"
    )

    return {
        "status": "success",
        "environment": environment,
        "bucket": bucket_name,
        "key": key,
        "local_output_path": local_output_path,
        "owner": owner,
    }
