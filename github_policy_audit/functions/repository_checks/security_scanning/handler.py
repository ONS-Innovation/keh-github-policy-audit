"""Lambda handler for the security scanning policy check."""

import logging

from policy_methods_library.checks.security_scanning import check_security_scanning
from utils.github import get_github_client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "...", "data": {...}}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])
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
