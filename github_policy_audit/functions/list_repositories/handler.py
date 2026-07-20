"""Lambda handler to list all repositories for a given owner."""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

from utils.github import get_github_client

from policy_methods_library.utils.pagination import get_paginated_list


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"owner": "...", "run_id": "...", "output_bucket": "..."}."""
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

    owner = event["owner"]
    run_id = event.get("run_id", "default-run")
    environment = os.environ.get("ENVIRONMENT", "local").lower()
    if environment not in {"local", "prod"}:
        raise ValueError("ENVIRONMENT must be either 'local' or 'prod'")

    bucket_name = event.get("output_bucket") or os.environ.get("S3_BUCKET_NAME")
    key = f"audit-runs/{owner}/{run_id}/repositories-list.json"

    output = {
        "owner": owner,
        "run_id": run_id,
        "repositories": repository_summaries,
        "repository_count": len(repository_summaries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    local_output_path = None
    if environment == "prod":
        if not bucket_name:
            raise ValueError("output_bucket (or S3_BUCKET_NAME) is required in prod")

        boto3.client("s3").put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(output, indent=2),
            ContentType="application/json",
        )
    else:
        output_dir = os.path.join("outputs", owner, run_id)
        os.makedirs(output_dir, exist_ok=True)
        local_output_path = os.path.join(output_dir, "repositories-list.json")

        with open(local_output_path, "w", encoding="utf-8") as file:
            json.dump(output, file, indent=2)

    logger.info(
        f"Lambda completed owner={owner} repositories_count={len(repository_summaries)} "
        f"storage=s3 bucket={bucket_name} key={key}"
    )

    return {
        "s3_bucket": bucket_name,
        "s3_key": key,
        "repository_count": len(repository_summaries),
        "environment": environment,
        "local_output_path": local_output_path,
    }
