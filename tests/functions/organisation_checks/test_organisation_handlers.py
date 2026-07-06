"""Unit tests for organisation-scoped Lambda check handlers."""

from __future__ import annotations

import importlib

import pytest


def test_dependabot_slo_handler_passes_levels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(
        "functions.organisation_checks.dependabot_slo.handler"
    )
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
    module = importlib.import_module(
        "functions.organisation_checks.dependabot_slo.handler"
    )
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
    module = importlib.import_module(
        "functions.organisation_checks.secret_scanning_slo.handler"
    )
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
    module = importlib.import_module(
        "functions.organisation_checks.team_maintainer.handler"
    )
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
