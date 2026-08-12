"""Lambda handler for the branch protection policy check."""

import logging

from policy_methods_library.checks.branch_protection import check_branch_protection
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""

    branches = client.make_request(
        "GET", f"/repos/{event['owner']}/{event['repository_name']}/branches"
    ).json()

    branch_name = None

    for branch in branches:
        if branch["name"] == "master":
            branch_name = "master"
            break
        elif branch["name"] == "main":
            branch_name = "main"
            break
        else:
            continue

    result = check_branch_protection(client, event["repository_name"], branch_name)

    result["check_name"] = "branch_protection"
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
