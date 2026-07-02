"""Lambda handler for the security scanning policy check."""

from policy_methods_library.checks.security_scanning import check_security_scanning
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
    client = get_github_client(event["owner"])
    result = check_security_scanning(client, event["repository_name"])
    result["check_name"] = "security_scanning"
    return result
