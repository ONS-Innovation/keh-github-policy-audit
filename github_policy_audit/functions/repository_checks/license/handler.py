"""Lambda handler for the license policy check."""

import logging

from policy_methods_library.checks.license import check_license
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    result = check_license(client, event["repository_name"])
    result["check_name"] = "license"
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
