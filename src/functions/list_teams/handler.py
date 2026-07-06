"""Lambda handler to list all teams for a given organisation."""

from utils.github import get_github_client

from policy_methods_library.utils.pagination import get_paginated_list


def handler(event, context):
    """Step Function invokes with {"owner": "..."}."""
    client = get_github_client(event["owner"])

    teams = get_paginated_list(
        client, f"/orgs/{event['owner']}/teams?per_page=100", "teams"
    )

    print(f"Found {len(teams)} teams for owner {event['owner']}")

    return teams
