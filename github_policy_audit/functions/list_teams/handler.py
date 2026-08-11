"""Lambda handler to list all teams for a given organisation."""

import logging

from utils.lambda_handler import github_handler
from utils.structured_logging import log_info

from policy_methods_library.utils.pagination import get_paginated_list


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _validate_team_list(payload: object) -> list[dict[str, object]]:
    """Validate paginated payload is a list of team-like objects."""
    if not isinstance(payload, list):
        if isinstance(payload, dict):
            payload_keys = ", ".join(sorted(str(key) for key in payload.keys()))
            raise TypeError(
                "Expected teams payload to be a list of objects, "
                f"got dict with keys: {payload_keys}.{' Error: ' + payload['error'] if 'error' in payload.keys() else ''}"
            )

        raise TypeError(
            "Expected teams payload to be a list of objects, "
            f"got {type(payload).__name__}"
        )

    invalid_item_index = next(
        (index for index, item in enumerate(payload) if not isinstance(item, dict)),
        None,
    )
    if invalid_item_index is not None:
        invalid_item = payload[invalid_item_index]
        raise TypeError(
            "Expected teams payload to contain only objects, "
            f"item at index {invalid_item_index} is {type(invalid_item).__name__}"
        )

    return payload


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "..."}."""
    teams_payload = get_paginated_list(
        client, f"/orgs/{event['owner']}/teams?per_page=100", "teams"
    )
    teams = _validate_team_list(teams_payload)

    # Downsize team objects to only include the slug and name, to reduce the size of the output.
    teams = [{"slug": team["slug"], "name": team["name"]} for team in teams]

    log_info(
        logger,
        "lambda_completed",
        owner=event["owner"],
        teams_count=len(teams),
    )

    return teams
