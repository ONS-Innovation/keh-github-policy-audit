"""Unit tests for repository-scoped Lambda check handlers."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from types import ModuleType

import pytest

REPO_CHECK_CASES = [
    (
        "functions.repository_checks.codeowners.handler",
        "check_codeowners",
        "codeowners",
    ),
    (
        "functions.repository_checks.dependabot.handler",
        "check_dependabot",
        "dependabot",
    ),
    (
        "functions.repository_checks.external_pull_request.handler",
        "check_external_pull_request",
        "external_pull_request",
    ),
    (
        "functions.repository_checks.gitignore.handler",
        "check_gitignore",
        "gitignore",
    ),
    (
        "functions.repository_checks.license.handler",
        "check_license",
        "license",
    ),
    (
        "functions.repository_checks.pirr.handler",
        "check_pirr",
        "pirr",
    ),
    (
        "functions.repository_checks.readme.handler",
        "check_readme",
        "readme",
    ),
    (
        "functions.repository_checks.repository_access.handler",
        "check_repository_access",
        "repository_access",
    ),
]


def _patch_handler_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    check_fn_name: str,
    check_impl: Callable,
) -> tuple[ModuleType, object]:
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
    module = importlib.import_module("functions.repository_checks.inactivity.handler")
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
    module = importlib.import_module("functions.repository_checks.inactivity.handler")
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
    module = importlib.import_module(
        "functions.repository_checks.security_scanning.handler"
    )
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
    module = importlib.import_module(
        "functions.repository_checks.security_scanning.handler"
    )
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


def test_naming_convention_handler_uses_repository_name_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(
        "functions.repository_checks.naming_convention.handler"
    )

    captured: dict[str, object] = {}

    def fake_check(repository_name: str) -> dict[str, object]:
        captured["repository_name"] = repository_name
        return {"status": "PASS"}

    monkeypatch.setattr(module, "check_naming_convention", fake_check)

    result = module.handler({"repository_name": "keh-github-policy-audit"}, None)

    assert captured == {"repository_name": "keh-github-policy-audit"}
    assert result == {"status": "PASS", "check_name": "naming_convention"}


def test_codeowners_handler_raises_for_missing_owner() -> None:
    module = importlib.import_module("functions.repository_checks.codeowners.handler")

    with pytest.raises(KeyError, match="owner"):
        module.handler({"repository_name": "keh-github-policy-audit"}, None)


def test_naming_convention_handler_raises_for_missing_repository_name() -> None:
    module = importlib.import_module(
        "functions.repository_checks.naming_convention.handler"
    )

    with pytest.raises(KeyError, match="repository_name"):
        module.handler({}, None)
