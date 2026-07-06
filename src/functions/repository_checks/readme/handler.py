"""Lambda handler for the readme policy check."""

from policy_methods_library.checks.readme import check_readme
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_readme(client, event["repository_name"])
    result["check_name"] = "readme"
    return result
