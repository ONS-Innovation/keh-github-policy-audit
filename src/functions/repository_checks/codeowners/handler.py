"""Lambda handler for the codeowners policy check."""

from policy_methods_library.checks.codeowners import check_codeowners
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_codeowners(client, event["repository_name"])
    result["check_name"] = "codeowners"
    return result
