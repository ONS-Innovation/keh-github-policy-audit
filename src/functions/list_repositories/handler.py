"""Lambda handler to list all repositories for a given owner."""

from utils.github import get_github_client

from policy_methods_library.utils.pagination import get_paginated_list


def handler(event, context):
    """Step Function invokes with {"owner": "..."}."""
    client = get_github_client(event["owner"])

    repositories = get_paginated_list(
        client, f"/orgs/{event['owner']}/repos?per_page=100", "repositories"
    )

    print(f"Found {len(repositories)} repositories for owner {event['owner']}")

    return repositories
