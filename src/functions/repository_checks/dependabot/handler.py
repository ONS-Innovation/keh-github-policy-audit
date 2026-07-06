"""Lambda handler for the dependabot policy check."""

from policy_methods_library.checks.dependabot import check_dependabot
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_dependabot(client, event["repository_name"])
    result["check_name"] = "dependabot"
    return result
