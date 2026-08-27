"""Lambda handler to list all teams for a given organisation."""

import json
import logging
import os

import boto3

from utils.lambda_handler import github_handler
from utils.structured_logging import log_info

from policy_methods_library.utils.pagination import get_paginated_list


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _validate_team_list(payload: object) -> list[dict[str, object]]:
    """Validate paginated payload is a list of team-like objects."""
    if not isinstance(payload, list):
        if isinstance(payload, dict):
            payload_keys = ", ".join(sorted(str(key) for key in payload.keys()))
            raise TypeError(
                "Expected teams payload to be a list of objects, "
                f"got dict with keys: {payload_keys}.{' Error: ' + payload['error'] if 'error' in payload.keys() else ''}"
            )

        raise TypeError(
            "Expected teams payload to be a list of objects, "
            f"got {type(payload).__name__}"
        )

    invalid_item_index = next(
        (index for index, item in enumerate(payload) if not isinstance(item, dict)),
        None,
    )
    if invalid_item_index is not None:
        invalid_item = payload[invalid_item_index]
        raise TypeError(
            "Expected teams payload to contain only objects, "
            f"item at index {invalid_item_index} is {type(invalid_item).__name__}"
        )

    return payload


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "run_id": "...", "output_bucket": "..."}."""
    teams_payload = get_paginated_list(
        client, f"/orgs/{event['owner']}/teams?per_page=100", "teams"
    )
    teams = _validate_team_list(teams_payload)

    # Downsize team objects to only include the slug and name, to reduce the size of the output.
    teams = [{"slug": team["slug"], "name": team["name"]} for team in teams]

    owner = event["owner"]
    run_id = event.get("run_id", "default-run")
    environment = os.environ.get("ENVIRONMENT", "local").lower()
    if environment not in {"local", "prod"}:
        raise ValueError("ENVIRONMENT must be either 'local' or 'prod'")

    bucket_name = event.get("output_bucket") or os.environ.get("S3_BUCKET_NAME")
    key = f"audit-runs/{owner}/{run_id}/teams-list.json"

    # Written as a bare JSON array so the Step Functions Map
    # can consume it directly if needed.
    local_output_path = None
    if environment == "prod":
        if not bucket_name:
            raise ValueError("output_bucket (or S3_BUCKET_NAME) is required in prod")

        boto3.client("s3").put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(teams, indent=2),
            ContentType="application/json",
        )
    else:
        output_dir = os.path.join("outputs", owner, run_id)
        os.makedirs(output_dir, exist_ok=True)
        local_output_path = os.path.join(output_dir, "teams-list.json")

        with open(local_output_path, "w", encoding="utf-8") as file:
            json.dump(teams, file, indent=2)

    log_info(
        logger,
        "lambda_completed",
        owner=owner,
        teams_count=len(teams),
        storage="s3" if environment == "prod" else "local",
        bucket=bucket_name,
        key=key,
    )

    return {
        "s3_bucket": bucket_name,
        "s3_key": key,
        "team_count": len(teams),
        "environment": environment,
        "local_output_path": local_output_path,
    }
