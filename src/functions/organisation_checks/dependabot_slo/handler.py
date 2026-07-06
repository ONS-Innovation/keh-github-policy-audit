"""Lambda handler for the dependabot SLO policy check."""

from policy_methods_library.checks.dependabot_slo import get_dependabot_slo
from utils.github import get_github_client


def handler(event, context):
    """Step Function invokes with {"owner": "...", "levels": ["critical", "high"]}.

    The levels field is optional and defaults to the policy library defaults.
    """
    client = get_github_client(event["owner"])
    result = get_dependabot_slo(client, event.get("levels"))
    result["check_name"] = "dependabot_slo"
    return result
