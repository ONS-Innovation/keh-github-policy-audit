"""Lambda handler to list all repositories for a given owner."""

import json
import logging
import os

import boto3

from utils.lambda_handler import github_handler
from utils.structured_logging import log_info

from policy_methods_library.utils.pagination import get_paginated_list


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _slim_security_and_analysis(security_and_analysis: dict | None) -> dict | None:
    """Return security_and_analysis with each feature reduced to {"status": ...}.

    The policy methods library only reads the 'status' sub-key from each feature.
    Dropping all other sub-keys (URLs, descriptions, etc.) significantly reduces
    the per-item size written to S3, keeping each item within the Step Functions
    256 KB distributed-map limit.
    """
    if not isinstance(security_and_analysis, dict):
        return security_and_analysis
    return {
        feature: {"status": details["status"]}
        for feature, details in security_and_analysis.items()
        if isinstance(details, dict) and "status" in details
    }


@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "run_id": "...", "output_bucket": "..."}."""
    repositories = get_paginated_list(
        client, f"/orgs/{event['owner']}/repos?per_page=100", "repositories"
    )
    repository_summaries = [
        {
            "name": repo["name"],
            "data": {
                "updated_at": repo.get("updated_at"),
                "visibility": repo.get("visibility"),
                "security_and_analysis": _slim_security_and_analysis(
                    repo.get("security_and_analysis")
                ),
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

    # Written as a bare JSON array so the Step Functions Distributed Map
    # ItemReader (InputType=JSON) can consume it directly without a path selector.
    local_output_path = None
    if environment == "prod":
        if not bucket_name:
            raise ValueError("output_bucket (or S3_BUCKET_NAME) is required in prod")

        boto3.client("s3").put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(repository_summaries, indent=2),
            ContentType="application/json",
        )
    else:
        output_dir = os.path.join("outputs", owner, run_id)
        os.makedirs(output_dir, exist_ok=True)
        local_output_path = os.path.join(output_dir, "repositories-list.json")

        with open(local_output_path, "w", encoding="utf-8") as file:
            json.dump(repository_summaries, file, indent=2)

    log_info(
        logger,
        "lambda_completed",
        owner=owner,
        repositories_count=len(repository_summaries),
        storage="s3" if environment == "prod" else "local",
        bucket=bucket_name,
        key=key,
    )

    return {
        "s3_bucket": bucket_name,
        "s3_key": key,
        "repository_count": len(repository_summaries),
        "environment": environment,
        "local_output_path": local_output_path,
    }
