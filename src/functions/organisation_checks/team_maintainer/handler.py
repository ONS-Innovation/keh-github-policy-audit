"""Lambda handler for the team maintainer policy check."""

from policy_methods_library.checks.team_maintainer import check_team_maintainer
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "team_slug": "..."}."""
    client = get_github_client(event["owner"])
    result = check_team_maintainer(client, event["team_slug"])
    result["check_name"] = "team_maintainer"
    return result
