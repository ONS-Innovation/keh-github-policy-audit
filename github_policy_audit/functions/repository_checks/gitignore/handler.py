"""Lambda handler for the gitignore policy check."""

import logging

from policy_methods_library.checks.gitignore import check_gitignore
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    result = check_gitignore(client, event["repository_name"])
    result["check_name"] = "gitignore"
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
