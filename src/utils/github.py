"""Shared GitHub utilities for Lambda handlers."""

import json
import os

import boto3

from policy_methods_library.github.clients import GitHubRestClient


def get_github_client(owner: str) -> GitHubRestClient:
    """Create a GitHubRestClient for the provided owner."""
    app_id_secret_name = os.environ["GITHUB_APP_ID_SECRET_NAME"]
    private_key_secret_name = os.environ["GITHUB_PRIVATE_KEY_SECRET_NAME"]

    secrets_manager = boto3.client("secretsmanager")
    app_id_secret = secrets_manager.get_secret_value(SecretId=app_id_secret_name)[
        "SecretString"
    ]
    private_key_secret = secrets_manager.get_secret_value(
        SecretId=private_key_secret_name
    )["SecretString"]

    try:
        app_id_secret = json.loads(app_id_secret)
    except json.JSONDecodeError:
        raise ValueError(
            f"Secret '{app_id_secret_name}' is not a valid JSON string. Please ensure the secret is key/value formatted."
        )

    app_id = app_id_secret.get("AppID")

    if not app_id:
        raise ValueError(
            f"Secret '{app_id_secret_name}' does not contain 'app_id'. Please ensure the secret is key/value formatted."
        )

    if not private_key_secret:
        raise ValueError(
            f"Secret '{private_key_secret_name}' is empty. Please ensure the secret contains a valid private key."
        )

    return GitHubRestClient(
        owner=owner,
        app_id=app_id,
        private_key=private_key_secret,
    )
