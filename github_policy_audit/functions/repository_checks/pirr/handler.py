"""Lambda handler for the PIRR policy check."""

import logging

from policy_methods_library.checks.pirr import check_pirr
from utils.github import get_github_client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])
    result = check_pirr(client, event["repository_name"])
    result["check_name"] = "pirr"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    return result
