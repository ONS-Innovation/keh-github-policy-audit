"""Lambda handler for the repository access policy check."""

import logging

from policy_methods_library.checks.repository_access import check_repository_access
from utils.lambda_handler import github_handler


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    result = check_repository_access(client, event["repository_name"])
    result["check_name"] = "repository_access"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    return result
