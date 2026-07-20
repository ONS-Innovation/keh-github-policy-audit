"""Lambda handler to load repository list from S3."""

import json
import logging

import boto3


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Load repositories from S3 written by list_repositories handler.

    Event should contain:
    {
        "s3_bucket": "...",
        "s3_key": "...",
        "repository_count": N
    }
    """
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")

    s3_bucket = event.get("s3_bucket")
    s3_key = event.get("s3_key")

    if not s3_bucket or not s3_key:
        raise ValueError("s3_bucket and s3_key are required in event")

    s3_client = boto3.client("s3")

    try:
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        content = json.loads(response["Body"].read().decode("utf-8"))
        repositories = content.get("repositories", [])

        logger.info(
            f"Loaded {len(repositories)} repositories from S3 "
            f"bucket={s3_bucket} key={s3_key}"
        )

        return repositories
    except Exception as e:
        logger.error(
            f"Failed to load repositories from S3: {e} bucket={s3_bucket} key={s3_key}"
        )
        raise
