"""Lambda handler for the dependabot SLO policy check."""

import logging

from policy_methods_library.checks.dependabot_slo import get_dependabot_slo
from utils.lambda_handler import github_handler


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "levels": ["critical", "high"]}.

    The levels field is optional and defaults to the policy library defaults.
    """
    result = get_dependabot_slo(client, event.get("levels"))
    result["check_name"] = "dependabot_slo"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    return result
