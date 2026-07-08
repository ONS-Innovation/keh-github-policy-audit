"""Tests for the local Lambda handler runner."""

from __future__ import annotations

from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

import run_handler


def test_parse_event_from_inline_json() -> None:
    """Parse inline JSON payloads into dictionaries."""
    event = run_handler.parse_event('{"owner": "ONS-Innovation"}', event_file=False)

    assert event == {"owner": "ONS-Innovation"}


def test_parse_event_from_file(tmp_path: Path) -> None:
    """Parse JSON payloads from files."""
    payload_file = tmp_path / "payload.json"
    payload_file.write_text('{"repository_name": "keh-github-policy-audit"}')

    event = run_handler.parse_event(str(payload_file), event_file=True)

    assert event == {"repository_name": "keh-github-policy-audit"}


def test_parse_event_rejects_non_object_payload() -> None:
    """Reject array payloads because handlers expect a JSON object."""
    with pytest.raises(ValueError, match="Event payload must be a JSON object"):
        run_handler.parse_event("[]", event_file=False)


def test_main_runs_handler_and_prints_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Call the requested handler and print JSON output when successful."""

    def fake_handler(event: dict[str, str], context: None) -> dict[str, object]:
        return {"status": "PASS", "echo": event}

    module = SimpleNamespace(handler=fake_handler)
    monkeypatch.setattr(run_handler.importlib, "import_module", lambda _: module)
    monkeypatch.setattr(
        run_handler.sys,
        "argv",
        [
            "run_handler.py",
            "functions.repository_checks.codeowners.handler",
            '{"owner":"ONS-Innovation"}',
        ],
    )

    exit_code = run_handler.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"status": "PASS"' in captured.out
    assert captured.err == ""


def test_main_returns_error_for_non_callable_handler(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fail cleanly if the selected attribute is not callable."""
    module = SimpleNamespace(handler="not-callable")
    monkeypatch.setattr(run_handler.importlib, "import_module", lambda _: module)
    monkeypatch.setattr(
        run_handler.sys,
        "argv",
        [
            "run_handler.py",
            "functions.repository_checks.codeowners.handler",
            '{"owner":"ONS-Innovation"}',
        ],
    )

    exit_code = run_handler.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "is not callable" in captured.err


def test_main_returns_error_when_handler_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Surface handler runtime exceptions as a non-zero exit code."""

    def failing_handler(event: dict[str, str], context: None) -> dict[str, str]:
        raise RuntimeError("boom")

    module = SimpleNamespace(handler=failing_handler)
    monkeypatch.setattr(run_handler.importlib, "import_module", lambda _: module)
    monkeypatch.setattr(
        run_handler.sys,
        "argv",
        [
            "run_handler.py",
            "functions.repository_checks.codeowners.handler",
            '{"owner":"ONS-Innovation"}',
        ],
    )

    exit_code = run_handler.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Handler raised an exception: boom" in captured.err


def test_main_returns_error_for_invalid_json_event(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fail with parse errors for malformed inline JSON."""
    monkeypatch.setattr(
        run_handler.sys,
        "argv",
        [
            "run_handler.py",
            "functions.repository_checks.codeowners.handler",
            "not-json",
        ],
    )

    exit_code = run_handler.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error:" in captured.err


def test_module_entrypoint_raises_system_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the module as __main__ so the entrypoint line is covered."""
    monkeypatch.setattr(
        run_handler.sys,
        "argv",
        [
            "run_handler.py",
            "json",
            "{}",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("run_handler", run_name="__main__")

    assert exc_info.value.code == 1
