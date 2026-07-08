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


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repositories": {...}, "teams": {...}, "organisation_checks": {...}}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")

    owner = event.get("owner")
    if not owner:
        raise ValueError("Event must include non-empty 'owner'")

    repositories = event.get("repositories") or {}
    teams = event.get("teams") or {}
    organisation_checks = event.get("organisation_checks") or {}

    if not isinstance(repositories, dict):
        raise ValueError("'repositories' must be a dictionary keyed by repository name")
    if not isinstance(teams, dict):
        raise ValueError("'teams' must be a dictionary keyed by team name")
    if not isinstance(organisation_checks, dict):
        raise ValueError("'organisation_checks' must be a dictionary")

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
