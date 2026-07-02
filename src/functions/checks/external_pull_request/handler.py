"""Lambda handler for the external pull request policy check."""

from policy_methods_library.checks.external_pull_request import check_external_pull_request
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_external_pull_request(client, event["repository_name"])
    result["check_name"] = "external_pull_request"
    return result
