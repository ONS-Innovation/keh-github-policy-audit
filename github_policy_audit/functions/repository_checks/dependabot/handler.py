"""Lambda handler for the dependabot policy check."""

import logging

from policy_methods_library.checks.dependabot import check_dependabot
from utils.lambda_handler import github_handler


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    result = check_dependabot(client, event["repository_name"])
    result["check_name"] = "dependabot"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    return result
