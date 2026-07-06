"""Lambda handler for the gitignore policy check."""

from policy_methods_library.checks.gitignore import check_gitignore
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_gitignore(client, event["repository_name"])
    result["check_name"] = "gitignore"
    return result
