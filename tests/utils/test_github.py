"""Tests for shared GitHub utilities."""

import json
import os
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from requests import Response
from requests.exceptions import HTTPError

from utils import github


@pytest.fixture(autouse=True)
def clear_client_cache() -> Generator[None, None, None]:
    """Ensure process-level client cache does not leak between tests."""
    github._CLIENT_CACHE.clear()
    github._SECRETS_MANAGER = None
    os.environ.pop("GITHUB_CLIENT_CACHE_TTL_SECONDS", None)
    yield
    github._CLIENT_CACHE.clear()
    github._SECRETS_MANAGER = None


def _response_with_status(status_code: int) -> Response:
    """Return a requests.Response configured with the provided status code."""
    response = Response()
    response.status_code = status_code
    return response


def _rate_limited_response() -> Response:
    """Return a 403 response carrying a rate-limit signal."""
    response = _response_with_status(403)
    response.headers["X-RateLimit-Remaining"] = "0"
    return response


class FakeSecretsManager:
    """Simple fake Secrets Manager client for unit tests."""

    def __init__(self, secrets_by_id: dict[str, str]) -> None:
        self.secrets_by_id = secrets_by_id
        self.requested_ids: list[str] = []

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803
        self.requested_ids.append(SecretId)
        return {"SecretString": self.secrets_by_id[SecretId]}


# get_github_client
# ---------------------------------------------------------------------------


class TestGetGithubClient:
    def test_returns_client_with_expected_values(self, rsa_private_key) -> None:
        """A valid secrets manager configuration should produce a correctly wired client."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        captured_kwargs: dict[str, Any] = {}

        def fake_github_rest_client(**kwargs: Any) -> dict[str, Any]:
            captured_kwargs.update(kwargs)
            return {"client": "ok"}

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", fake_github_rest_client),
        ):
            result = github.get_github_client("ONS-Innovation")

        assert result == {"client": "ok"}
        assert captured_kwargs == {
            "owner": "ONS-Innovation",
            "app_id": "123456",
            "private_key": rsa_private_key,
        }
        assert fake_secrets_manager.requested_ids == [
            "app-id-secret",
            "private-key-secret",
        ]

    def test_raises_for_non_json_app_id_secret(self, rsa_private_key) -> None:
        """A non-JSON app ID secret should raise a ValueError."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": "not-json",
                "private-key-secret": rsa_private_key,
            }
        )

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
        ):
            with pytest.raises(ValueError, match="not a valid JSON string"):
                github.get_github_client("ONS-Innovation")

    def test_raises_when_app_id_missing(self, rsa_private_key) -> None:
        """An app ID secret that lacks the expected key should raise a ValueError."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"wrong-key": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
        ):
            with pytest.raises(ValueError, match="does not contain 'AppID'"):
                github.get_github_client("ONS-Innovation")

    def test_raises_when_private_key_empty(self) -> None:
        """An empty private key secret should raise a ValueError."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": "",
            }
        )

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
        ):
            with pytest.raises(ValueError, match="is empty"):
                github.get_github_client("ONS-Innovation")

    def test_raises_for_missing_required_env_var(self) -> None:
        """A missing required environment variable should raise a KeyError."""
        for missing_env_var in [
            "GITHUB_APP_ID_SECRET_NAME",
            "GITHUB_PRIVATE_KEY_SECRET_NAME",
        ]:
            with patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ):
                os.environ.pop(missing_env_var)
                with pytest.raises(
                    KeyError, match="Missing required environment variable"
                ):
                    github.get_github_client("ONS-Innovation")

    def test_strips_owner_before_building_client(self, rsa_private_key) -> None:
        """Leading/trailing whitespace in owner should be removed before client creation."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        captured_kwargs: dict[str, Any] = {}

        def fake_github_rest_client(**kwargs: Any) -> dict[str, Any]:
            captured_kwargs.update(kwargs)
            return {"client": "ok"}

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", fake_github_rest_client),
        ):
            github.get_github_client("  ONS-Innovation  ")

        assert captured_kwargs["owner"] == "ONS-Innovation"

    def test_raises_for_non_string_owner(self, rsa_private_key) -> None:
        """A non-string owner should raise a ValueError before any API calls."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
        ):
            with pytest.raises(ValueError, match="owner must be a string"):
                github.get_github_client(None)  # type: ignore[arg-type]

    def test_raises_for_empty_owner(self, rsa_private_key) -> None:
        """An empty owner should raise a ValueError before any API calls."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
        ):
            with pytest.raises(ValueError, match="owner must not be empty"):
                github.get_github_client("   ")

    def test_retries_transient_http_error_during_client_init(
        self, rsa_private_key
    ) -> None:
        """Rate-limited 403 responses should be retried before succeeding."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        call_count = {"value": 0}

        def flaky_github_rest_client(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            call_count["value"] += 1
            if call_count["value"] < 2:
                raise HTTPError("Forbidden", response=_rate_limited_response())
            return {"client": "ok"}

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", flaky_github_rest_client),
            patch.object(github.time, "sleep") as mocked_sleep,
            patch.object(github.random, "uniform", return_value=0.0),
        ):
            result = github.get_github_client("ONS-Innovation")

        assert result == {"client": "ok"}
        assert call_count["value"] == 2
        mocked_sleep.assert_called_once_with(0.5)

    def test_does_not_retry_non_retryable_http_error(self, rsa_private_key) -> None:
        """Non-retryable HTTP errors should be raised immediately."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(
                github,
                "GitHubRestClient",
                side_effect=HTTPError(
                    "Unauthorized", response=_response_with_status(401)
                ),
            ),
        ):
            with pytest.raises(HTTPError, match="Unauthorized"):
                github.get_github_client("ONS-Innovation")

    def test_attempts_final_client_init_after_exhausting_retries(
        self, rsa_private_key
    ) -> None:
        """After retry loop exhaustion for rate limits, perform one final init attempt."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        call_count = {"value": 0}

        def eventually_successful_client(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            call_count["value"] += 1
            if call_count["value"] <= 3:
                raise HTTPError("Forbidden", response=_rate_limited_response())
            return {"client": "ok-final"}

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", eventually_successful_client),
            patch.object(github.time, "sleep") as mocked_sleep,
            patch.object(github.random, "uniform", return_value=0.0),
        ):
            result = github.get_github_client("ONS-Innovation")

        assert result == {"client": "ok-final"}
        assert call_count["value"] == 4
        assert mocked_sleep.call_count == 3

    def test_retries_plain_403_for_installation_token_endpoint(
        self, rsa_private_key
    ) -> None:
        """Installation token endpoint 403 should be treated as retryable."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        call_count = {"value": 0}

        def installation_token_then_success(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            call_count["value"] += 1
            if call_count["value"] == 1:
                response = _response_with_status(403)
                response.url = (
                    "https://api.github.com/app/installations/123/access_tokens"
                )
                error = HTTPError("Forbidden", response=response)
                error.request = type(
                    "Request",
                    (),
                    {
                        "url": "https://api.github.com/app/installations/123/access_tokens"
                    },
                )()
                raise error

            return {"client": "ok"}

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", installation_token_then_success),
            patch.object(github.time, "sleep") as mocked_sleep,
            patch.object(github.random, "uniform", return_value=0.0),
        ):
            result = github.get_github_client("ONS-Innovation")

        assert result == {"client": "ok"}
        assert call_count["value"] == 2
        mocked_sleep.assert_called_once_with(0.5)

    def test_does_not_retry_non_rate_limited_403(self, rsa_private_key) -> None:
        """A plain 403 should fail fast (likely auth/permission issue)."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        call_count = {"value": 0}

        def forbidden_client(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            call_count["value"] += 1
            raise HTTPError("Forbidden", response=_response_with_status(403))

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", forbidden_client),
            patch.object(github.time, "sleep") as mocked_sleep,
        ):
            with pytest.raises(HTTPError, match="Forbidden"):
                github.get_github_client("ONS-Innovation")

        assert call_count["value"] == 1
        mocked_sleep.assert_not_called()

    def test_logs_error_context_for_non_retryable_error(self, rsa_private_key) -> None:
        """Non-retryable errors should log URL and body snippet for diagnostics."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        forbidden_response = _response_with_status(403)

        def forbidden_with_context(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            error = HTTPError("Forbidden", response=forbidden_response)
            error.request = type(
                "Request",
                (),
                {"url": "https://api.github.com/app/installations/123/access_tokens"},
            )()
            raise error

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", forbidden_with_context),
        ):
            with pytest.raises(HTTPError):
                github.get_github_client("ONS-Innovation")

    def test_reuses_cached_client_within_ttl(self, rsa_private_key) -> None:
        """Subsequent calls in the same runtime should reuse the cached client."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        call_count = {"value": 0}

        def fake_github_rest_client(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            call_count["value"] += 1
            return {"client": f"ok-{call_count['value']}"}

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", fake_github_rest_client),
            patch.object(github.time, "monotonic", side_effect=[10.0, 20.0]),
        ):
            first = github.get_github_client("ONS-Innovation")
            second = github.get_github_client("ONS-Innovation")

        assert first is second
        assert call_count["value"] == 1
        assert fake_secrets_manager.requested_ids == [
            "app-id-secret",
            "private-key-secret",
        ]

    def test_refreshes_cached_client_after_ttl_expiry(self, rsa_private_key) -> None:
        """Expired cache entries should trigger a new client initialisation."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        call_count = {"value": 0}

        def fake_github_rest_client(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            call_count["value"] += 1
            return {"client": f"ok-{call_count['value']}"}

        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_APP_ID_SECRET_NAME": "app-id-secret",
                    "GITHUB_PRIVATE_KEY_SECRET_NAME": "private-key-secret",
                    "GITHUB_CLIENT_CACHE_TTL_SECONDS": "1",
                },
            ),
            patch.object(github.boto3, "client", return_value=fake_secrets_manager),
            patch.object(github, "GitHubRestClient", fake_github_rest_client),
            patch.object(github.time, "monotonic", side_effect=[0.0, 5.0, 6.0]),
        ):
            first = github.get_github_client("ONS-Innovation")
            second = github.get_github_client("ONS-Innovation")

        assert first != second
        assert call_count["value"] == 2
        assert fake_secrets_manager.requested_ids == [
            "app-id-secret",
            "private-key-secret",
            "app-id-secret",
            "private-key-secret",
        ]


class TestGithubRateLimitHelpers:
    def test_is_retryable_http_error_returns_true_for_retry_after_header(self) -> None:
        """A 403 with Retry-After should be treated as retryable."""
        response = _response_with_status(403)
        response.headers["Retry-After"] = "30"

        error = HTTPError("Forbidden", response=response)

        assert github._is_retryable_http_error(error) is True

    def test_is_retryable_http_error_returns_true_for_retryable_non_403(self) -> None:
        """Retryable status codes other than 403 should return True."""
        error = HTTPError("Too Many Requests", response=_response_with_status(429))

        assert github._is_retryable_http_error(error) is True

    def test_is_retryable_http_error_returns_true_for_rate_limit_body(self) -> None:
        """A 403 with a rate-limit body signal should be treated as retryable."""
        response = _response_with_status(403)
        response._content = b"API rate limit exceeded for this endpoint"

        error = HTTPError("Forbidden", response=response)

        assert github._is_retryable_http_error(error) is True

    def test_is_retryable_http_error_returns_true_for_abuse_detection_body(
        self,
    ) -> None:
        """A 403 with an abuse-detection body should be treated as retryable."""
        response = _response_with_status(403)
        response._content = (
            b'{"message": "You have triggered an abuse detection mechanism. '
            b'Please wait a few minutes before you try again."}'
        )

        error = HTTPError("Forbidden", response=response)

        assert github._is_retryable_http_error(error) is True

    def test_is_retryable_http_error_returns_true_for_secondary_rate_limit_body(
        self,
    ) -> None:
        """A 403 with a secondary rate-limit body should be treated as retryable."""
        response = _response_with_status(403)
        response._content = (
            b'{"message": "You have exceeded a secondary rate limit and have been '
            b'temporarily blocked from content creation."}'
        )

        error = HTTPError("Forbidden", response=response)

        assert github._is_retryable_http_error(error) is True

    def test_is_retryable_http_error_returns_true_for_installation_token_403(
        self,
    ) -> None:
        """A plain 403 for app installation token creation should be retryable."""
        response = _response_with_status(403)
        response.url = "https://api.github.com/app/installations/123/access_tokens"

        error = HTTPError("Forbidden", response=response)
        error.request = type(
            "Request",
            (),
            {"url": "https://api.github.com/app/installations/123/access_tokens"},
        )()

        assert github._is_retryable_http_error(error) is True


class TestGithubCacheTtlHelpers:
    def test_get_client_cache_ttl_seconds_invalid_value_uses_default(self) -> None:
        """Invalid TTL env values should fall back to default and log a warning."""
        with (
            patch.dict(os.environ, {"GITHUB_CLIENT_CACHE_TTL_SECONDS": "not-a-number"}),
            patch.object(github, "log_warning") as mocked_log_warning,
        ):
            ttl = github._get_client_cache_ttl_seconds()

        assert ttl == github._DEFAULT_CLIENT_CACHE_TTL_SECONDS
        mocked_log_warning.assert_called_once()
        assert mocked_log_warning.call_args.kwargs["provided_value"] == "not-a-number"

    def test_get_client_cache_ttl_seconds_non_positive_uses_default(self) -> None:
        """Non-positive TTL env values should fall back to default and log a warning."""
        with (
            patch.dict(os.environ, {"GITHUB_CLIENT_CACHE_TTL_SECONDS": "0"}),
            patch.object(github, "log_warning") as mocked_log_warning,
        ):
            ttl = github._get_client_cache_ttl_seconds()

        assert ttl == github._DEFAULT_CLIENT_CACHE_TTL_SECONDS
        mocked_log_warning.assert_called_once()
        assert mocked_log_warning.call_args.kwargs["provided_value"] == "0"
