"""Lambda handler for the license policy check."""

from policy_methods_library.checks.license import check_license
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_license(client, event["repository_name"])
    result["check_name"] = "license"
    return result
