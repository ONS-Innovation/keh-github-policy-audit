"""Lambda handler for the security scanning policy check."""

import logging

from policy_methods_library.checks.security_scanning import check_security_scanning
from utils.lambda_handler import fail_on_error_result
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "...", "data": {...}}."""
    result = check_security_scanning(
        client,
        event["repository_name"],
        data=event.get("data"),
    )
    result["check_name"] = "security_scanning"
    fail_on_error_result(result, result["check_name"])
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
