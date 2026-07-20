"""Lambda handler for the dependabot SLO policy check."""

import logging

from policy_methods_library.checks.dependabot_slo import get_dependabot_slo
from utils.github import get_github_client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "...", "levels": ["critical", "high"]}.

    The levels field is optional and defaults to the policy library defaults.
    """
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])
    result = get_dependabot_slo(client, event.get("levels"))
    result["check_name"] = "dependabot_slo"
    logger.info(
        f"Lambda completed check={result['check_name']} status={result.get('status')}"
    )
    return result
