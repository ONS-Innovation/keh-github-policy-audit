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
        "functions.checks.inactivity.handler",
        "check_inactivity",
        "inactivity",
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
    (
        "functions.checks.security_scanning.handler",
        "check_security_scanning",
        "security_scanning",
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


def test_codeowners_handler_raises_for_missing_owner() -> None:
    module = importlib.import_module("functions.checks.codeowners.handler")

    with pytest.raises(KeyError, match="owner"):
        module.handler({"repository_name": "keh-github-policy-audit"}, None)


def test_naming_convention_handler_raises_for_missing_repository_name() -> None:
    module = importlib.import_module("functions.checks.naming_convention.handler")

    with pytest.raises(KeyError, match="repository_name"):
        module.handler({}, None)
