"""Tests for shared GitHub utilities."""

import json
import logging
import os
from typing import Any
from unittest.mock import patch

import pytest
from requests import Response
from requests.exceptions import HTTPError

from utils import github


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
        ):
            result = github.get_github_client("ONS-Innovation")

        assert result == {"client": "ok-final"}
        assert call_count["value"] == 4
        assert mocked_sleep.call_count == 3

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

    @pytest.mark.parametrize(
        "payload, expected",
        [
            ("not-a-dict", (None, None)),
            ({}, (None, None)),
            (_response_with_status(200), (None, None)),
            ({"resources": "not-a-dict"}, (None, None)),
            ({"resources": {}}, (None, None)),
            ({"resources": {"core": "not-a-dict"}}, (None, None)),
            (
                {"resources": {"core": {"remaining": 4999, "reset": 1700000000}}},
                (4999, 1700000000),
            ),
        ],
    )
    def test_extract_rate_limit_fields(
        self, payload: Any, expected: tuple[Any, Any]
    ) -> None:
        """Rate-limit field extraction should be robust across malformed payloads."""
        assert github._extract_rate_limit_fields(payload) == expected

    def test_extract_rate_limit_fields_from_response(self) -> None:
        """Rate-limit field extraction should support requests.Response payloads."""
        response = _response_with_status(200)
        response._content = json.dumps(
            {"resources": {"core": {"remaining": 4999, "reset": 1700000000}}}
        ).encode("utf-8")

        assert github._extract_rate_limit_fields(response) == (4999, 1700000000)


class TestLogStepRateLimit:
    def test_module_logger_is_configured_for_info(self) -> None:
        """The utility logger should emit INFO records in Lambda by default."""
        assert github.logger.level == logging.INFO

    def test_raises_for_invalid_phase(self) -> None:
        """Invalid phase values should raise ValueError."""
        client = object()
        with pytest.raises(ValueError, match="phase must be either 'start' or 'end'"):
            github.log_step_rate_limit(client, "middle", "tests.step")  # type: ignore[arg-type]

    def test_logs_rate_limit_when_request_succeeds(self) -> None:
        """Successful /rate_limit requests should log remaining and reset."""

        class FakeClient:
            def make_request(self, method: str, path: str) -> dict[str, Any]:
                assert method == "GET"
                assert path == "/rate_limit"
                return {
                    "resources": {
                        "core": {
                            "remaining": 1234,
                            "reset": 1712345678,
                        }
                    }
                }

        with patch.object(github.logger, "info") as mocked_info:
            github.log_step_rate_limit(FakeClient(), "start", "tests.step")

        mocked_info.assert_called_once_with(
            "GitHub rate limit step=%s phase=%s remaining=%s reset=%s",
            "tests.step",
            "start",
            1234,
            1712345678,
        )

    def test_logs_unknown_fields_when_payload_missing_values(self) -> None:
        """Missing rate-limit fields should be logged as unknown."""

        class FakeClient:
            def make_request(self, method: str, path: str) -> dict[str, Any]:
                assert method == "GET"
                assert path == "/rate_limit"
                return {}

        with patch.object(github.logger, "info") as mocked_info:
            github.log_step_rate_limit(FakeClient(), "end", "tests.step")

        mocked_info.assert_called_once_with(
            "GitHub rate limit step=%s phase=%s remaining=%s reset=%s",
            "tests.step",
            "end",
            "unknown",
            "unknown",
        )

    def test_logs_warning_when_request_fails(self) -> None:
        """Errors when reading /rate_limit should log a warning and not raise."""

        class FakeClient:
            def make_request(self, method: str, path: str) -> dict[str, Any]:
                assert method == "GET"
                assert path == "/rate_limit"
                raise RuntimeError("boom")

        with patch.object(github.logger, "warning") as mocked_warning:
            github.log_step_rate_limit(FakeClient(), "start", "tests.step")

        mocked_warning.assert_called_once()
