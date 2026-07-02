"""Shared GitHub utilities for Lambda handlers."""

import json
import os

import boto3

from policy_methods_library.github.clients import GitHubRestClient

def get_github_client(owner: str) -> GitHubRestClient:
    """Create a GitHubRestClient for the provided owner."""
    secret_name = os.environ["GITHUB_SECRET_NAME"]
    secrets_manager = boto3.client("secretsmanager")
    secret = json.loads(
        secrets_manager.get_secret_value(SecretId=secret_name)["SecretString"]
    )
    return GitHubRestClient(
        owner=owner,
        app_id=secret["app_id"],
        private_key=secret["private_key"],
    )
