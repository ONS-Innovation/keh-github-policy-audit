"""Lambda handler for the external pull request policy check."""

import logging

from policy_methods_library.checks.external_pull_request import (
    check_external_pull_request,
)
from utils.lambda_handler import fail_on_error_result
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    result = check_external_pull_request(client, event["repository_name"])
    result["check_name"] = "external_pull_request"
    fail_on_error_result(result, result["check_name"])
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
