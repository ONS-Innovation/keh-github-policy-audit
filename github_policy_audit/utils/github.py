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
logger.setLevel(logging.INFO)

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
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code not in _RETRYABLE_STATUS_CODES:
        return False

    # Most 403s here are permanent auth/permission issues and should fail fast.
    # Retry 403 only for clear rate-limit signals.
    if status_code == 403:
        headers = getattr(response, "headers", {}) or {}
        rate_limit_remaining = headers.get("X-RateLimit-Remaining")
        if rate_limit_remaining == "0":
            return True

        retry_after = headers.get("Retry-After")
        if retry_after:
            return True

        response_body = ""
        try:
            text = getattr(response, "text", "")
            response_body = (text or "").lower()
        except Exception:  # pragma: no cover
            response_body = ""

        return "rate limit" in response_body

    return True


def _http_error_context(error: HTTPError) -> tuple[str, str]:
    """Return URL and a short response body snippet for diagnostic logging."""
    response = getattr(error, "response", None)
    url = getattr(getattr(error, "request", None), "url", "unknown")

    body_snippet = ""
    if response is not None:
        try:
            text = getattr(response, "text", "")
            body_snippet = (text or "")[:300].replace("\n", " ")
        except Exception:  # pragma: no cover
            body_snippet = ""

    return url, body_snippet


def _extract_rate_limit_fields(rate_limit_payload: Any) -> tuple[Any, Any]:
    """Extract remaining and reset values from a GitHub /rate_limit payload."""
    if hasattr(rate_limit_payload, "json") and callable(rate_limit_payload.json):
        try:
            rate_limit_payload = rate_limit_payload.json()
        except ValueError:
            return None, None

    if not isinstance(rate_limit_payload, dict):
        return None, None

    resources = rate_limit_payload.get("resources")
    if not isinstance(resources, dict):
        return None, None

    core = resources.get("core")
    if not isinstance(core, dict):
        return None, None

    return core.get("remaining"), core.get("reset")


def log_step_rate_limit(
    github_client: GitHubRestClient, phase: str, step_name: str
) -> None:
    """Log the GitHub API rate limit at a step boundary.

    This helper must never raise, to avoid masking handler failures.
    """
    if phase not in {"start", "end"}:
        raise ValueError("phase must be either 'start' or 'end'")

    try:
        rate_limit_payload = github_client.make_request("GET", "/rate_limit")
        remaining, reset = _extract_rate_limit_fields(rate_limit_payload)
        logger.info(
            "GitHub rate limit step=%s phase=%s remaining=%s reset=%s",
            step_name,
            phase,
            remaining if remaining is not None else "unknown",
            reset if reset is not None else "unknown",
        )
    except Exception as error:
        logger.warning(
            "Unable to read GitHub rate limit step=%s phase=%s error=%s",
            step_name,
            phase,
            error,
        )


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
            f"Secret '{app_id_secret_name}' does not contain 'AppID'. Please ensure the secret is key/value formatted."
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
                status_code = getattr(error.response, "status_code", "unknown")
                url, body_snippet = _http_error_context(error)
                logger.error(
                    "GitHub client initialisation failed owner=%s status=%s url=%s app_id_secret=%s private_key_secret=%s body=%s",
                    owner,
                    status_code,
                    url,
                    app_id_secret_name,
                    private_key_secret_name,
                    body_snippet,
                )
                raise

            status_code = getattr(error.response, "status_code", "unknown")
            url, body_snippet = _http_error_context(error)
            logger.warning(
                "Transient GitHub client initialisation error for owner=%s status=%s url=%s attempt=%s/%s. Retrying in %.1fs. body=%s",
                owner,
                status_code,
                url,
                attempt,
                len(_CLIENT_INIT_RETRY_DELAYS_SECONDS),
                delay,
                body_snippet,
            )
            time.sleep(delay)

    return GitHubRestClient(**client_kwargs)
