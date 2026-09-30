"""Lambda handler for the branch protection policy check."""

import logging

from policy_methods_library.checks.branch_protection import check_branch_protection
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "...", "data": {...}}."""

    branch_name = event["data"]["default_branch"]

    result = check_branch_protection(client, event["repository_name"], branch_name)

    result["check_name"] = "branch_protection"
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
