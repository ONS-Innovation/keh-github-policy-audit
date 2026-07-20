"""Lambda handler for the team maintainer policy check."""

import logging

from policy_methods_library.checks.team_maintainer import check_team_maintainer
from utils.github import get_github_client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "...", "team_slug": "..."}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])
    result = check_team_maintainer(client, event["team_slug"])
    result["check_name"] = "team_maintainer"
    logger.info(
        f"Lambda completed check={result['check_name']} status={result.get('status')}"
    )
    return result
