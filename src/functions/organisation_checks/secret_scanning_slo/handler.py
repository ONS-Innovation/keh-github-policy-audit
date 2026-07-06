"""Lambda handler for the secret scanning SLO policy check."""

import logging

from policy_methods_library.checks.secret_scanning_slo import get_secret_scanning_slo
from utils.github import get_github_client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "..."}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])
    result = get_secret_scanning_slo(client)
    result["check_name"] = "secret_scanning_slo"
    logger.info(
        f"Lambda completed check={result['check_name']} status={result.get('status')}"
    )
    return result
