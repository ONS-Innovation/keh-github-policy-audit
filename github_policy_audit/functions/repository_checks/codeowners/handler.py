"""Lambda handler for the codeowners policy check."""

import logging

from policy_methods_library.checks.codeowners import check_codeowners
from utils.lambda_handler import github_handler


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    result = check_codeowners(client, event["repository_name"])
    result["check_name"] = "codeowners"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    return result
