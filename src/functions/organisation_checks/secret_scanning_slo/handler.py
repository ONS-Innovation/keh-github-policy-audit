"""Lambda handler for the secret scanning SLO policy check."""

from policy_methods_library.checks.secret_scanning_slo import get_secret_scanning_slo
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "..."}."""
    client = get_github_client(event["owner"])
    result = get_secret_scanning_slo(client)
    result["check_name"] = "secret_scanning_slo"
    return result
