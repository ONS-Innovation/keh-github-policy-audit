"""Lambda handler for the secret scanning SLO policy check."""

import logging

from policy_methods_library.checks.secret_scanning_slo import get_secret_scanning_slo
from utils.lambda_handler import github_handler


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "..."}."""
    result = get_secret_scanning_slo(client)
    result["check_name"] = "secret_scanning_slo"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    return result
