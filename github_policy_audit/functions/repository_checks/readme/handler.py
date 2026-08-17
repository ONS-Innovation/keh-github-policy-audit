"""Lambda handler for the readme policy check."""

import logging

from policy_methods_library.checks.readme import check_readme
from utils.lambda_handler import fail_on_error_result
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    result = check_readme(client, event["repository_name"])
    result["check_name"] = "readme"
    fail_on_error_result(result, result["check_name"])
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
