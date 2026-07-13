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
                "security_and_analysis": repo.get("security_and_analysis"),
            },
        }
        for repo in repositories
        if repo.get("name")
    ]

    logger.info(
        f"Lambda completed owner={event['owner']} repositories_count={len(repository_summaries)}"
    )

    return repository_summaries
