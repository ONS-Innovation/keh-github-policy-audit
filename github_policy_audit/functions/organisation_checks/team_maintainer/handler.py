"""Lambda handler for the team maintainer policy check."""

import logging

from policy_methods_library.checks.team_maintainer import check_team_maintainer
from utils.lambda_handler import github_handler


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "team_slug": "..."}."""
    result = check_team_maintainer(client, event["team_slug"])
    result["check_name"] = "team_maintainer"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )

    result.pop("details", None)  # Remove details from the result to reduce payload size
    return result
