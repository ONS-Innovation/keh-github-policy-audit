"""Unit tests for Lambda check handlers."""

from __future__ import annotations

import importlib
from collections.abc import Callable

import pytest

REPO_CHECK_CASES = [
    (
        "functions.checks.codeowners.handler",
        "check_codeowners",
        "codeowners",
    ),
    (
        "functions.checks.dependabot.handler",
        "check_dependabot",
        "dependabot",
    ),
    (
        "functions.checks.external_pull_request.handler",
        "check_external_pull_request",
        "external_pull_request",
    ),
    (
        "functions.checks.gitignore.handler",
        "check_gitignore",
        "gitignore",
    ),
    (
        "functions.checks.license.handler",
        "check_license",
        "license",
    ),
    (
        "functions.checks.pirr.handler",
        "check_pirr",
        "pirr",
    ),
    (
        "functions.checks.readme.handler",
        "check_readme",
        "readme",
    ),
    (
        "functions.checks.repository_access.handler",
        "check_repository_access",
        "repository_access",
    ),
]


def _patch_handler_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    check_fn_name: str,
    check_impl: Callable,
) -> tuple[object, object]:
    module = importlib.import_module(module_name)
    client = object()
    monkeypatch.setattr(module, "get_github_client", lambda owner: client)
    monkeypatch.setattr(module, check_fn_name, check_impl)
    return module, client


@pytest.mark.parametrize(
    ("module_name", "check_fn_name", "check_name"),
    REPO_CHECK_CASES,
)
def test_repository_scoped_handlers_wire_client_and_repo(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    check_fn_name: str,
    check_name: str,
) -> None:
    captured: dict[str, object] = {}

    def fake_check(client: object, repository_name: str) -> dict[str, object]:
        captured["client"] = client
        captured["repository_name"] = repository_name
        return {"status": "PASS"}

    module, expected_client = _patch_handler_dependencies(
        monkeypatch,
        module_name,
        check_fn_name,
        fake_check,
    )

    result = module.handler(
        {"owner": "ONS-Innovation", "repository_name": "keh-github-policy-audit"},
        None,
    )

    assert captured == {
        "client": expected_client,
        "repository_name": "keh-github-policy-audit",
    }
    assert result == {"status": "PASS", "check_name": check_name}


def test_inactivity_handler_passes_event_data_for_flat_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.inactivity.handler")
    client = object()
    monkeypatch.setattr(module, "get_github_client", lambda owner: client)

    captured: dict[str, object] = {}
    event = {
        "owner": "ONS-Innovation",
        "repository_name": "keh-github-policy-audit",
        "data": {"updated_at": "2026-07-03T10:00:00Z"},
    }

    def fake_check(
        check_client: object,
        repository_name: str,
        data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        captured["client"] = check_client
        captured["repository_name"] = repository_name
        captured["data"] = data
        return {"status": "PASS"}

    monkeypatch.setattr(module, "check_inactivity", fake_check)

    result = module.handler(event, None)

    assert captured == {
        "client": client,
        "repository_name": "keh-github-policy-audit",
        "data": {"updated_at": "2026-07-03T10:00:00Z"},
    }
    assert result == {"status": "PASS", "check_name": "inactivity"}


def test_inactivity_handler_passes_none_when_data_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.inactivity.handler")
    client = object()
    event = {
        "owner": "ONS-Innovation",
        "repository_name": "keh-github-policy-audit",
    }

    monkeypatch.setattr(module, "get_github_client", lambda owner: client)
    captured: dict[str, object] = {}

    def fake_check(
        check_client: object,
        repository_name: str,
        data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        captured["client"] = check_client
        captured["repository_name"] = repository_name
        captured["data"] = data
        return {"status": "PASS"}

    monkeypatch.setattr(module, "check_inactivity", fake_check)

    result = module.handler(event, None)

    assert captured == {
        "client": client,
        "repository_name": "keh-github-policy-audit",
        "data": None,
    }
    assert result == {"status": "PASS", "check_name": "inactivity"}


def test_security_scanning_handler_passes_event_data_for_flat_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.security_scanning.handler")
    client = object()
    monkeypatch.setattr(module, "get_github_client", lambda owner: client)

    captured: dict[str, object] = {}
    event = {
        "owner": "ONS-Innovation",
        "repository_name": "keh-github-policy-audit",
        "data": {"security_and_analysis": {"secret_scanning": {"status": "enabled"}}},
    }

    def fake_check(
        check_client: object,
        repository_name: str,
        data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        captured["client"] = check_client
        captured["repository_name"] = repository_name
        captured["data"] = data
        return {"status": "PASS"}

    monkeypatch.setattr(module, "check_security_scanning", fake_check)

    result = module.handler(event, None)

    assert captured == {
        "client": client,
        "repository_name": "keh-github-policy-audit",
        "data": {"security_and_analysis": {"secret_scanning": {"status": "enabled"}}},
    }
    assert result == {"status": "PASS", "check_name": "security_scanning"}


def test_security_scanning_handler_passes_none_when_data_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.security_scanning.handler")
    client = object()
    event = {
        "owner": "ONS-Innovation",
        "repository_name": "keh-github-policy-audit",
    }

    monkeypatch.setattr(module, "get_github_client", lambda owner: client)
    captured: dict[str, object] = {}

    def fake_check(
        check_client: object,
        repository_name: str,
        data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        captured["client"] = check_client
        captured["repository_name"] = repository_name
        captured["data"] = data
        return {"status": "PASS"}

    monkeypatch.setattr(module, "check_security_scanning", fake_check)

    result = module.handler(event, None)

    assert captured == {
        "client": client,
        "repository_name": "keh-github-policy-audit",
        "data": None,
    }
    assert result == {"status": "PASS", "check_name": "security_scanning"}


def test_dependabot_slo_handler_passes_levels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.dependabot_slo.handler")
    client = object()
    monkeypatch.setattr(module, "get_github_client", lambda owner: client)

    captured: dict[str, object] = {}

    def fake_check(check_client: object, levels: list[str] | None) -> dict[str, object]:
        captured["client"] = check_client
        captured["levels"] = levels
        return {"status": "PASS"}

    monkeypatch.setattr(module, "get_dependabot_slo", fake_check)

    result = module.handler(
        {"owner": "ONS-Innovation", "levels": ["critical", "high"]},
        None,
    )

    assert captured == {"client": client, "levels": ["critical", "high"]}
    assert result == {"status": "PASS", "check_name": "dependabot_slo"}


def test_dependabot_slo_handler_defaults_levels_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.dependabot_slo.handler")
    client = object()
    monkeypatch.setattr(module, "get_github_client", lambda owner: client)

    captured: dict[str, object] = {}

    def fake_check(check_client: object, levels: list[str] | None) -> dict[str, object]:
        captured["client"] = check_client
        captured["levels"] = levels
        return {"status": "PASS"}

    monkeypatch.setattr(module, "get_dependabot_slo", fake_check)

    result = module.handler({"owner": "ONS-Innovation"}, None)

    assert captured == {"client": client, "levels": None}
    assert result == {"status": "PASS", "check_name": "dependabot_slo"}


def test_secret_scanning_slo_handler_wires_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.secret_scanning_slo.handler")
    client = object()
    monkeypatch.setattr(module, "get_github_client", lambda owner: client)

    captured: dict[str, object] = {}

    def fake_check(check_client: object) -> dict[str, object]:
        captured["client"] = check_client
        return {"status": "PASS"}

    monkeypatch.setattr(module, "get_secret_scanning_slo", fake_check)

    result = module.handler({"owner": "ONS-Innovation"}, None)

    assert captured == {"client": client}
    assert result == {"status": "PASS", "check_name": "secret_scanning_slo"}


def test_team_maintainer_handler_wires_team_slug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.team_maintainer.handler")
    client = object()
    monkeypatch.setattr(module, "get_github_client", lambda owner: client)

    captured: dict[str, object] = {}

    def fake_check(check_client: object, team_slug: str) -> dict[str, object]:
        captured["client"] = check_client
        captured["team_slug"] = team_slug
        return {"status": "PASS"}

    monkeypatch.setattr(module, "check_team_maintainer", fake_check)

    result = module.handler(
        {"owner": "ONS-Innovation", "team_slug": "keh-dev"},
        None,
    )

    assert captured == {"client": client, "team_slug": "keh-dev"}
    assert result == {"status": "PASS", "check_name": "team_maintainer"}


def test_naming_convention_handler_uses_repository_name_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("functions.checks.naming_convention.handler")

    captured: dict[str, object] = {}

    def fake_check(repository_name: str) -> dict[str, object]:
        captured["repository_name"] = repository_name
        return {"status": "PASS"}

    monkeypatch.setattr(module, "check_naming_convention", fake_check)

    result = module.handler({"repository_name": "keh-github-policy-audit"}, None)

    assert captured == {"repository_name": "keh-github-policy-audit"}
    assert result == {"status": "PASS", "check_name": "naming_convention"}


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


def test_codeowners_handler_raises_for_missing_owner() -> None:
    module = importlib.import_module("functions.checks.codeowners.handler")

    with pytest.raises(KeyError, match="owner"):
        module.handler({"repository_name": "keh-github-policy-audit"}, None)


def test_naming_convention_handler_raises_for_missing_repository_name() -> None:
    module = importlib.import_module("functions.checks.naming_convention.handler")

    with pytest.raises(KeyError, match="repository_name"):
        module.handler({}, None)


def test_list_repositories_handler_raises_for_missing_owner() -> None:
    module = importlib.import_module("functions.list_repositories.handler")

    with pytest.raises(KeyError, match="owner"):
        module.handler({}, None)
