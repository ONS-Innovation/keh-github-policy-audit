"""Lambda handler for the naming convention policy check."""

import logging

from policy_methods_library.checks.naming_convention import check_naming_convention
from utils.lambda_handler import fail_on_error_result
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"repository_name": "..."}."""
    log_info(logger, "lambda_invoked", event_keys=sorted(event.keys()))
    result = check_naming_convention(event["repository_name"])
    result["check_name"] = "naming_convention"
    fail_on_error_result(result, result["check_name"])
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
