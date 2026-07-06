"""Unit tests for repository listing handler."""

from __future__ import annotations

import importlib

import pytest


def test_list_repositories_handler_fetches_paginated_repositories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.list_repositories.handler")
    client = object()
    monkeypatch.setattr(module, "get_github_client", lambda owner: client)

    captured: dict[str, object] = {}

    def fake_get_paginated_list(
        check_client: object,
        endpoint: str,
        result_key: str,
    ) -> list[dict[str, str]]:
        captured["client"] = check_client
        captured["endpoint"] = endpoint
        captured["result_key"] = result_key
        return [{"name": "keh-github-policy-audit"}]

    monkeypatch.setattr(module, "get_paginated_list", fake_get_paginated_list)

    result = module.handler({"owner": "ONS-Innovation"}, None)

    assert captured == {
        "client": client,
        "endpoint": "/orgs/ONS-Innovation/repos?per_page=100",
        "result_key": "repositories",
    }
    assert result == [{"name": "keh-github-policy-audit"}]


def test_list_repositories_handler_raises_for_missing_owner() -> None:
    module = importlib.import_module("functions.list_repositories.handler")

    with pytest.raises(KeyError, match="owner"):
        module.handler({}, None)
