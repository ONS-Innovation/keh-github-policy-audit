"""Lambda handler for the dependabot policy check."""

import logging

from policy_methods_library.checks.dependabot import check_dependabot
from utils.github import get_github_client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])
    result = check_dependabot(client, event["repository_name"])
    result["check_name"] = "dependabot"
    logger.info(
        f"Lambda completed check={result['check_name']} status={result.get('status')}"
    )
    return result
