"""Shared GitHub utilities for Lambda handlers."""

import json
import logging
import os
import time
from typing import Any

import boto3
from requests.exceptions import HTTPError

from policy_methods_library.github.clients import GitHubRestClient


logger = logging.getLogger(__name__)

# Transient errors can occur when many Lambdas request installation tokens in parallel.
_CLIENT_INIT_RETRY_DELAYS_SECONDS = [0.5, 1.0, 2.0]
_RETRYABLE_STATUS_CODES = {403, 429, 500, 502, 503, 504}


def _normalise_owner(owner: str) -> str:
    if not isinstance(owner, str):
        raise ValueError("owner must be a string")

    normalised_owner = owner.strip()
    if not normalised_owner:
        raise ValueError("owner must not be empty")

    return normalised_owner


def _is_retryable_http_error(error: HTTPError) -> bool:
    status_code = getattr(error.response, "status_code", None)
    return status_code in _RETRYABLE_STATUS_CODES


def get_github_client(owner: str) -> GitHubRestClient:
    """Create a GitHubRestClient for the provided owner."""
    owner = _normalise_owner(owner)

    try:
        app_id_secret_name = os.environ["GITHUB_APP_ID_SECRET_NAME"]
        private_key_secret_name = os.environ["GITHUB_PRIVATE_KEY_SECRET_NAME"]
    except KeyError as e:
        raise KeyError(
            f"Missing required environment variable: {e}. Please ensure the Lambda function has the necessary environment variables set."
        ) from e

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

    client_kwargs: dict[str, Any] = {
        "owner": owner,
        "app_id": app_id,
        "private_key": private_key_secret,
    }

    for attempt, delay in enumerate(_CLIENT_INIT_RETRY_DELAYS_SECONDS, start=1):
        try:
            return GitHubRestClient(**client_kwargs)
        except HTTPError as error:
            if not _is_retryable_http_error(error):
                raise

            status_code = getattr(error.response, "status_code", "unknown")
            logger.warning(
                "Transient GitHub client initialisation error for owner=%s status=%s attempt=%s/%s. Retrying in %.1fs.",
                owner,
                status_code,
                attempt,
                len(_CLIENT_INIT_RETRY_DELAYS_SECONDS),
                delay,
            )
            time.sleep(delay)

    return GitHubRestClient(**client_kwargs)
