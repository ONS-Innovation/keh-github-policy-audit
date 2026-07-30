"""Lambda handler for the inactivity policy check."""

import logging

from policy_methods_library.checks.inactivity import check_inactivity
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "...", "data": {...}}."""
    result = check_inactivity(
        client,
        event["repository_name"],
        data=event.get("data"),
    )
    result["check_name"] = "inactivity"
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
