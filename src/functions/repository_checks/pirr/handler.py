"""Lambda handler for the PIRR policy check."""

from policy_methods_library.checks.pirr import check_pirr
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_pirr(client, event["repository_name"])
    result["check_name"] = "pirr"
    return result
