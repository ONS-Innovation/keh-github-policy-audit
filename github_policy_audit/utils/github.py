"""Shared GitHub utilities for Lambda handlers."""

import json
import logging
import os
import random
import time
from typing import Any
from urllib.parse import urlparse

import boto3
from requests.exceptions import HTTPError

from policy_methods_library.github.clients import GitHubRestClient
from utils.structured_logging import log_error, log_warning


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Transient errors can occur when many Lambdas request installation tokens in parallel.
_CLIENT_INIT_RETRY_DELAYS_SECONDS = [0.5, 1.0, 2.0]
_RETRYABLE_STATUS_CODES = {403, 429, 500, 502, 503, 504}
_CLIENT_INIT_JITTER_FACTOR = 0.25
_DEFAULT_CLIENT_CACHE_TTL_SECONDS = 300.0
_CLIENT_CACHE: dict[str, tuple[float, GitHubRestClient]] = {}


def _normalise_owner(owner: str) -> str:
    if not isinstance(owner, str):
        raise ValueError("owner must be a string")

    normalised_owner = owner.strip()
    if not normalised_owner:
        raise ValueError("owner must not be empty")

    return normalised_owner


def _http_error_url(error: HTTPError) -> str:
    request_url = getattr(getattr(error, "request", None), "url", "")
    if request_url:
        return request_url

    return getattr(getattr(error, "response", None), "url", "") or ""


def _is_installation_access_token_url(url: str) -> bool:
    if not url:
        return False

    path = urlparse(url).path
    return path.startswith("/app/installations/") and path.endswith("/access_tokens")


def _retry_delay_with_jitter(base_delay_seconds: float) -> float:
    jitter = random.uniform(0.0, base_delay_seconds * _CLIENT_INIT_JITTER_FACTOR)
    return base_delay_seconds + jitter


def _get_client_cache_ttl_seconds() -> float:
    ttl_value = os.getenv("GITHUB_CLIENT_CACHE_TTL_SECONDS")
    if ttl_value is None:
        return _DEFAULT_CLIENT_CACHE_TTL_SECONDS

    try:
        ttl_seconds = float(ttl_value)
    except ValueError:
        log_warning(
            logger,
            "github_client_cache_ttl_invalid",
            provided_value=ttl_value,
            default_ttl_seconds=_DEFAULT_CLIENT_CACHE_TTL_SECONDS,
        )
        return _DEFAULT_CLIENT_CACHE_TTL_SECONDS

    if ttl_seconds <= 0:
        log_warning(
            logger,
            "github_client_cache_ttl_non_positive",
            provided_value=ttl_value,
            default_ttl_seconds=_DEFAULT_CLIENT_CACHE_TTL_SECONDS,
        )
        return _DEFAULT_CLIENT_CACHE_TTL_SECONDS

    return ttl_seconds


def _get_cached_client(owner: str) -> GitHubRestClient | None:
    cached = _CLIENT_CACHE.get(owner)
    if cached is None:
        return None

    cached_at, client = cached
    ttl_seconds = _get_client_cache_ttl_seconds()
    if (time.monotonic() - cached_at) <= ttl_seconds:
        return client

    _CLIENT_CACHE.pop(owner, None)
    return None


def _cache_client(owner: str, client: GitHubRestClient) -> None:
    _CLIENT_CACHE[owner] = (time.monotonic(), client)


def _is_retryable_http_error(error: HTTPError) -> bool:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code not in _RETRYABLE_STATUS_CODES:
        return False

    # Most 403s here are permanent auth/permission issues and should fail fast.
    # Retry 403 only for clear rate-limit signals.
    if status_code == 403:
        url = _http_error_url(error)
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

        if "rate limit" in response_body:
            return True

        # GitHub App installation token creation can return transient 403 responses
        # (for example, burst/abuse protection) without explicit rate-limit headers.
        return _is_installation_access_token_url(url)

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


def get_github_client(owner: str) -> GitHubRestClient:
    """Create a GitHubRestClient for the provided owner."""
    owner = _normalise_owner(owner)

    cached_client = _get_cached_client(owner)
    if cached_client is not None:
        return cached_client

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
            client = GitHubRestClient(**client_kwargs)
            _cache_client(owner, client)
            return client
        except HTTPError as error:
            if not _is_retryable_http_error(error):
                status_code = getattr(error.response, "status_code", "unknown")
                url, body_snippet = _http_error_context(error)
                log_error(
                    logger,
                    "github_client_initialisation_failed",
                    owner=owner,
                    status=status_code,
                    url=url,
                    app_id_secret=app_id_secret_name,
                    private_key_secret=private_key_secret_name,
                    body=body_snippet,
                )
                raise

            retry_delay_seconds = _retry_delay_with_jitter(delay)
            status_code = getattr(error.response, "status_code", "unknown")
            url, body_snippet = _http_error_context(error)
            log_warning(
                logger,
                "github_client_initialisation_retry",
                owner=owner,
                status=status_code,
                url=url,
                attempt=attempt,
                max_attempts=len(_CLIENT_INIT_RETRY_DELAYS_SECONDS),
                base_retry_delay_seconds=delay,
                retry_delay_seconds=retry_delay_seconds,
                body=body_snippet,
            )
            time.sleep(retry_delay_seconds)

    client = GitHubRestClient(**client_kwargs)
    _cache_client(owner, client)
    return client
