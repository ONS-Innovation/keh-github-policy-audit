"""Lambda handler to store per-repository check results."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _normalise_environment(raw_environment: str | None) -> str:
    """Normalise supported environments."""
    environment = (raw_environment or "local").lower()
    if environment in {"local", "prod"}:
        return environment
    raise ValueError("ENVIRONMENT must be either 'local' or 'prod'")


def _normalise_checks(checks: Any) -> dict[str, dict]:
    """Return checks as a dictionary keyed by check_name."""
    if isinstance(checks, dict):
        return checks

    if not isinstance(checks, list):
        raise ValueError("'checks' must be a dictionary or list")

    checks_by_name: dict[str, dict] = {}
    for check_result in checks:
        if not isinstance(check_result, dict):
            continue
        check_name = check_result.get("check_name")
        if isinstance(check_name, str) and check_name:
            checks_by_name[check_name] = check_result

    return checks_by_name


def handler(event, context):
    """Store a repository-level result object and return an S3 pointer."""
    log_info(logger, "lambda_invoked", event_keys=sorted(event.keys()))

    owner = event["owner"]
    repository_name = event["repository_name"]
    run_id = event["run_id"]

    checks = _normalise_checks(event.get("checks", []))

    environment = _normalise_environment(os.environ.get("ENVIRONMENT", "local"))

    bucket_name = event.get("output_bucket") or os.environ.get("S3_BUCKET_NAME")
    key = f"audit-runs/{owner}/{run_id}/repositories/{repository_name}.json"

    output = {
        "owner": owner,
        "run_id": run_id,
        "repository_name": repository_name,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    local_output_path = None
    if environment == "prod":
        if not bucket_name:
            raise ValueError("output_bucket (or S3_BUCKET_NAME) is required in prod")

        boto3.client("s3").put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(output, indent=2),
            ContentType="application/json",
        )
    else:
        output_dir = os.path.join(
            "outputs", "audit-runs", owner, run_id, "repositories"
        )
        os.makedirs(output_dir, exist_ok=True)
        local_output_path = os.path.join(output_dir, f"{repository_name}.json")

        with open(local_output_path, "w", encoding="utf-8") as file:
            json.dump(output, file, indent=2)

    log_info(
        logger,
        "stored_repository_result",
        owner=owner,
        run_id=run_id,
        repository_name=repository_name,
        checks_count=len(checks),
    )

    return {
        "status": "success",
        "environment": environment,
        "bucket": bucket_name,
        "key": key,
        "local_output_path": local_output_path,
        "owner": owner,
        "run_id": run_id,
        "repository_name": repository_name,
    }
