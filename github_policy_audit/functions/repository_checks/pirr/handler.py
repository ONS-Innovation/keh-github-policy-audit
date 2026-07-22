"""Lambda handler for the PIRR policy check."""

import logging

from policy_methods_library.checks.pirr import check_pirr
from utils.github import get_github_client, log_step_rate_limit


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])
    log_step_rate_limit(client, "start", __name__)
    result = check_pirr(client, event["repository_name"])
    result["check_name"] = "pirr"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    log_step_rate_limit(client, "end", __name__)
    return result
