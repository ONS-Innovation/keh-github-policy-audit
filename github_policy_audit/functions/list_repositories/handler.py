"""Lambda handler to list all repositories for a given owner."""

import logging

from utils.github import get_github_client

from policy_methods_library.utils.pagination import get_paginated_list


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "..."}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    client = get_github_client(event["owner"])

    repositories = get_paginated_list(
        client, f"/orgs/{event['owner']}/repos?per_page=100", "repositories"
    )
    repository_summaries = [
        {
            "name": repo["name"],
            "data": {
                "updated_at": repo.get("updated_at"),
                "visibility": repo.get("visibility"),
                "security_and_analysis": repo.get("security_and_analysis"),
            },
        }
        for repo in repositories
        if repo.get("name") and not repo.get("archived", False)
        # This is a pretty wasteful way to filter out archived repos since it still has to be fetched from the API. REST API does not support filtering by archived status
        # so this is the only way to do it without switching to the GraphQL API. This shouldn't add too much execution time. 3000 repos at 1 second per 100 repos is 30 seconds, which is acceptable for this use case.
        # Switching to GraphQL would reduce this to 1500 repos at 1 second per 100 repos, which is 15 seconds. 15 seconds isn't worth the effort of introducing and maintaining a GraphQL client for this use case.
    ]

    logger.info(
        f"Lambda completed owner={event['owner']} repositories_count={len(repository_summaries)}"
    )

    return repository_summaries
