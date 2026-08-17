"""Lambda handler for the dependabot SLO policy check."""

import logging

from policy_methods_library.checks.dependabot_slo import get_dependabot_slo
from utils.lambda_handler import fail_on_error_result
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "levels": ["critical", "high"]}.

    The levels field is optional and defaults to the policy library defaults.
    """
    result = get_dependabot_slo(client, event.get("levels"))
    result["check_name"] = "dependabot_slo"
    fail_on_error_result(result, result["check_name"])
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
