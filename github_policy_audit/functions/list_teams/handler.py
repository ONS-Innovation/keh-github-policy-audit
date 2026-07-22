"""Lambda handler to list all teams for a given organisation."""

import logging

from utils.lambda_handler import github_handler
from utils.structured_logging import log_info

from policy_methods_library.utils.pagination import get_paginated_list


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "..."}."""
    teams = get_paginated_list(
        client, f"/orgs/{event['owner']}/teams?per_page=100", "teams"
    )

    # Downsize team objects to only include the slug and name, to reduce the size of the output.
    teams = [{"slug": team["slug"], "name": team["name"]} for team in teams]

    log_info(
        logger,
        "lambda_completed",
        owner=event["owner"],
        teams_count=len(teams),
    )

    return teams
