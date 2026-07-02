"""Lambda handler for the inactivity policy check."""

from policy_methods_library.checks.inactivity import check_inactivity
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_inactivity(client, event["repository_name"])
    result["check_name"] = "inactivity"
    return result
