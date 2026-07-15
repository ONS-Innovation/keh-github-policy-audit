"""Tests for shared GitHub utilities."""

import json
import os
from typing import Any
from unittest.mock import patch

import pytest
from requests.exceptions import HTTPError

from utils import github


class FakeSecretsManager:
    """Simple fake Secrets Manager client for unit tests."""

    def __init__(self, secrets_by_id: dict[str, str]) -> None:
        self.secrets_by_id = secrets_by_id
        self.requested_ids: list[str] = []

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803
        self.requested_ids.append(SecretId)
        return {"SecretString": self.secrets_by_id[SecretId]}


# ---------------------------------------------------------------------------
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
            with pytest.raises(ValueError, match="does not contain 'app_id'"):
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
        """Transient HTTP errors should be retried before succeeding."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        class FakeResponse:
            status_code = 403

        call_count = {"value": 0}

        def flaky_github_rest_client(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            call_count["value"] += 1
            if call_count["value"] < 2:
                raise HTTPError("Forbidden", response=FakeResponse())
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

        class FakeResponse:
            status_code = 401

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
                side_effect=HTTPError("Unauthorized", response=FakeResponse()),
            ),
        ):
            with pytest.raises(HTTPError, match="Unauthorized"):
                github.get_github_client("ONS-Innovation")

    def test_attempts_final_client_init_after_exhausting_retries(
        self, rsa_private_key
    ) -> None:
        """After retry loop exhaustion, get_github_client should perform one final init attempt."""
        fake_secrets_manager = FakeSecretsManager(
            {
                "app-id-secret": json.dumps({"AppID": "123456"}),
                "private-key-secret": rsa_private_key,
            }
        )

        class FakeResponse:
            status_code = 403

        call_count = {"value": 0}

        def eventually_successful_client(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            call_count["value"] += 1
            if call_count["value"] <= 3:
                raise HTTPError("Forbidden", response=FakeResponse())
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
