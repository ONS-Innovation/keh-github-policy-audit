"""Lambda handler to list all teams for a given organisation."""

import logging

from utils.github import get_github_client, log_step_rate_limit

from policy_methods_library.utils.pagination import get_paginated_list


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "..."}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])
    log_step_rate_limit(client, "start", __name__)

    teams = get_paginated_list(
        client, f"/orgs/{event['owner']}/teams?per_page=100", "teams"
    )

    # Downsize team objects to only include the slug and name, to reduce the size of the output.
    teams = [{"slug": team["slug"], "name": team["name"]} for team in teams]

    logger.info(f"Lambda completed owner={event['owner']} teams_count={len(teams)}")
    log_step_rate_limit(client, "end", __name__)

    return teams
