"""Lambda handler for the secret scanning SLO policy check."""

import json
import logging
from typing import Any

import boto3

from policy_methods_library.checks.secret_scanning_slo import get_secret_scanning_slo
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _load_repository_names(repository_s3_ref: dict[str, Any]) -> list[str]:
    """Load the non-archived repository names written by list_repositories."""
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
    """Step Function invokes with {"owner": "..."}."""
    if event.get("repositories_s3_ref"):
        repository_names = _load_repository_names(event["repositories_s3_ref"])
        result = get_secret_scanning_slo(client, repository_names=repository_names)
    else:
        result = get_secret_scanning_slo(client)

    result["check_name"] = "secret_scanning_slo"
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
