"""Tests for shared GitHub utilities."""

from __future__ import annotations

import json
from typing import Any

import pytest

from utils import github


class FakeSecretsManager:
    """Simple fake Secrets Manager client for unit tests."""

    def __init__(self, secrets_by_id: dict[str, str]) -> None:
        self.secrets_by_id = secrets_by_id
        self.requested_ids: list[str] = []

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803
        self.requested_ids.append(SecretId)
        return {"SecretString": self.secrets_by_id[SecretId]}


def test_get_github_client_returns_client_with_expected_values(
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: str,
) -> None:
    """Construct a GitHub client with parsed app ID and plain-text private key."""
    monkeypatch.setenv("GITHUB_APP_ID_SECRET_NAME", "app-id-secret")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_SECRET_NAME", "private-key-secret")

    fake_secrets_manager = FakeSecretsManager(
        {
            "app-id-secret": json.dumps({"AppID": "123456"}),
            "private-key-secret": rsa_private_key,
        }
    )

    monkeypatch.setattr(github.boto3, "client", lambda _: fake_secrets_manager)

    captured_kwargs: dict[str, Any] = {}

    def fake_github_rest_client(**kwargs: Any) -> dict[str, Any]:
        captured_kwargs.update(kwargs)
        return {"client": "ok"}

    monkeypatch.setattr(github, "GitHubRestClient", fake_github_rest_client)

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


def test_get_github_client_raises_for_non_json_app_id_secret(
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: str,
) -> None:
    """Reject app ID secrets that are not JSON."""
    monkeypatch.setenv("GITHUB_APP_ID_SECRET_NAME", "app-id-secret")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_SECRET_NAME", "private-key-secret")

    fake_secrets_manager = FakeSecretsManager(
        {
            "app-id-secret": "not-json",
            "private-key-secret": rsa_private_key,
        }
    )

    monkeypatch.setattr(github.boto3, "client", lambda _: fake_secrets_manager)

    with pytest.raises(ValueError, match="not a valid JSON string"):
        github.get_github_client("ONS-Innovation")


def test_get_github_client_raises_when_app_id_missing(
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: str,
) -> None:
    """Reject app ID secrets that do not contain the required AppID key."""
    monkeypatch.setenv("GITHUB_APP_ID_SECRET_NAME", "app-id-secret")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_SECRET_NAME", "private-key-secret")

    fake_secrets_manager = FakeSecretsManager(
        {
            "app-id-secret": json.dumps({"wrong-key": "123456"}),
            "private-key-secret": rsa_private_key,
        }
    )

    monkeypatch.setattr(github.boto3, "client", lambda _: fake_secrets_manager)

    with pytest.raises(ValueError, match="does not contain 'app_id'"):
        github.get_github_client("ONS-Innovation")


def test_get_github_client_raises_when_private_key_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject empty private-key secrets."""
    monkeypatch.setenv("GITHUB_APP_ID_SECRET_NAME", "app-id-secret")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_SECRET_NAME", "private-key-secret")

    fake_secrets_manager = FakeSecretsManager(
        {
            "app-id-secret": json.dumps({"AppID": "123456"}),
            "private-key-secret": "",
        }
    )

    monkeypatch.setattr(github.boto3, "client", lambda _: fake_secrets_manager)

    with pytest.raises(ValueError, match="is empty"):
        github.get_github_client("ONS-Innovation")
