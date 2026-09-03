"""Lambda handler for the dependabot SLO policy check."""

import json
import logging
import os
from pathlib import Path
from typing import Any

import boto3

from policy_methods_library.checks.dependabot_slo import get_dependabot_slo
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _load_repository_names(event: dict[str, Any]) -> list[str]:
    """Load the non-archived repository names written by list_repositories."""
    if os.environ.get("ENVIRONMENT", "local").lower() == "local" and event.get(
        "run_id"
    ):
        path = (
            Path("outputs")
            / "audit-runs"
            / event["owner"]
            / event["run_id"]
            / "repositories-list.json"
        )
        with path.open(encoding="utf-8") as file:
            repositories = json.load(file)
    else:
        repository_s3_ref = event["repositories_s3_ref"]
        response = boto3.client("s3").get_object(
            Bucket=repository_s3_ref["s3_bucket"], Key=repository_s3_ref["s3_key"]
        )
        repositories = json.loads(response["Body"].read())
    return [
        repository["name"]
        for repository in repositories
        if isinstance(repository, dict) and isinstance(repository.get("name"), str)
    ]


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "levels": ["critical", "high"]}.

    The levels field is optional and defaults to the policy library defaults.
    """
    if event.get("repositories_s3_ref") or event.get("run_id"):
        repository_names = _load_repository_names(event)
        result = get_dependabot_slo(
            client, event.get("levels"), repository_names=repository_names
        )
    else:
        result = get_dependabot_slo(client, event.get("levels"))

    result["check_name"] = "dependabot_slo"
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
