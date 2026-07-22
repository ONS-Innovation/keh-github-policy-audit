"""Lambda handler for the security scanning policy check."""

import logging

from policy_methods_library.checks.security_scanning import check_security_scanning
from utils.lambda_handler import github_handler


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
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    return result
