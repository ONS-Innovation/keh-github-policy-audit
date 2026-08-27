"""Lambda handler to store organisation-level check results to S3."""

import json
import logging
import os
from datetime import datetime, timezone

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


def handler(event, context):
    """Store an organisation-level check result object and return an S3 pointer.

    Event format: {
        "owner": "...",
        "run_id": "...",
        "output_bucket": "...",
        "check_name": "dependabot_slo|secret_scanning_slo",
        "result": "pass|fail",
        "message": "...",
        "details": {...}  (optional)
    }
    """
    log_info(logger, "lambda_invoked", event_keys=sorted(event.keys()))

    owner = event["owner"]
    run_id = event["run_id"]
    check_name = event["check_name"]

    environment = _normalise_environment(os.environ.get("ENVIRONMENT", "local"))

    bucket_name = event.get("output_bucket") or os.environ.get("S3_BUCKET_NAME")
    key = f"audit-runs/{owner}/{run_id}/organisation-checks/{check_name}.json"

    output = {
        "owner": owner,
        "run_id": run_id,
        "check_name": check_name,
        "result": event.get("result"),
        "message": event.get("message"),
        "details": event.get("details", {}),
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
        output_dir = os.path.join("outputs", owner, run_id, "organisation-checks")
        os.makedirs(output_dir, exist_ok=True)
        local_output_path = os.path.join(output_dir, f"{check_name}.json")

        with open(local_output_path, "w", encoding="utf-8") as file:
            json.dump(output, file, indent=2)

    log_info(
        logger,
        "stored_organisation_check_result",
        owner=owner,
        run_id=run_id,
        check_name=check_name,
    )

    return {
        "status": "success",
        "environment": environment,
        "bucket": bucket_name,
        "key": key,
        "check_name": check_name,
        "local_output_path": local_output_path,
    }
