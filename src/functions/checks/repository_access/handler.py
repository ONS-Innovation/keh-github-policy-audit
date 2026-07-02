"""Lambda handler for the repository access policy check."""

from policy_methods_library.checks.repository_access import check_repository_access
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_repository_access(client, event["repository_name"])
    result["check_name"] = "repository_access"
    return result
