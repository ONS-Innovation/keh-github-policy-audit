"""Tests for the local Lambda handler runner."""

import io
import runpy
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import run_handler


# ---------------------------------------------------------------------------
# parse_event
# ---------------------------------------------------------------------------


class TestParseEvent:
    def test_parse_event_from_inline_json(self):
        """An inline JSON string should be parsed directly into a dict."""
        event = run_handler.parse_event('{"owner": "ONS-Innovation"}', event_file=False)
        assert event == {"owner": "ONS-Innovation"}

    def test_parse_event_from_file(self):
        """A file path should be read and its JSON contents parsed into a dict."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload_file = Path(tmp_dir) / "payload.json"
            payload_file.write_text('{"repository_name": "keh-github-policy-audit"}')
            event = run_handler.parse_event(str(payload_file), event_file=True)
        assert event == {"repository_name": "keh-github-policy-audit"}

    def test_parse_event_rejects_non_object_payload(self):
        """A non-object JSON payload should raise a ValueError."""
        with pytest.raises(ValueError, match="Event payload must be a JSON object"):
            run_handler.parse_event("[]", event_file=False)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain:
    def test_runs_handler_and_prints_result(self):
        """A successful handler invocation should print the result and return exit code 0."""

        def fake_handler(event: dict, context: None) -> dict:
            return {"status": "PASS", "echo": event}

        module = SimpleNamespace(handler=fake_handler)

        with (
            patch(
                "sys.argv",
                [
                    "run_handler.py",
                    "functions.repository_checks.codeowners.handler",
                    '{"owner":"ONS-Innovation"}',
                ],
            ),
            patch("sys.stdout", new_callable=io.StringIO) as mock_stdout,
            patch("sys.stderr", new_callable=io.StringIO) as mock_stderr,
            patch.object(run_handler.importlib, "import_module", return_value=module),
        ):
            exit_code = run_handler.main()
            out = mock_stdout.getvalue()
            err = mock_stderr.getvalue()

        assert exit_code == 0
        assert '"status": "PASS"' in out
        assert err == ""

    def test_returns_error_for_non_callable_handler(self):
        """A non-callable handler attribute should return exit code 1 with an error message."""
        module = SimpleNamespace(handler="not-callable")

        with (
            patch(
                "sys.argv",
                [
                    "run_handler.py",
                    "functions.repository_checks.codeowners.handler",
                    '{"owner":"ONS-Innovation"}',
                ],
            ),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as mock_stderr,
            patch.object(run_handler.importlib, "import_module", return_value=module),
        ):
            exit_code = run_handler.main()
            err = mock_stderr.getvalue()

        assert exit_code == 1
        assert "is not callable" in err

    def test_returns_error_when_handler_raises(self):
        """An exception raised by the handler should return exit code 1 with an error message."""

        def failing_handler(event: dict, context: None) -> dict:
            raise RuntimeError("boom")

        module = SimpleNamespace(handler=failing_handler)

        with (
            patch(
                "sys.argv",
                [
                    "run_handler.py",
                    "functions.repository_checks.codeowners.handler",
                    '{"owner":"ONS-Innovation"}',
                ],
            ),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as mock_stderr,
            patch.object(run_handler.importlib, "import_module", return_value=module),
        ):
            exit_code = run_handler.main()
            err = mock_stderr.getvalue()

        assert exit_code == 1
        assert "Handler raised an exception: boom" in err

    def test_returns_error_for_invalid_json_event(self):
        """An invalid JSON event string should return exit code 1 with an error message."""
        with (
            patch(
                "sys.argv",
                [
                    "run_handler.py",
                    "functions.repository_checks.codeowners.handler",
                    "not-json",
                ],
            ),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as mock_stderr,
        ):
            exit_code = run_handler.main()
            err = mock_stderr.getvalue()

        assert exit_code == 1
        assert "Error:" in err

    def test_module_entrypoint_raises_system_exit(self):
        """Running run_handler as __main__ should raise SystemExit on failure."""
        with patch("sys.argv", ["run_handler.py", "json", "{}"]):
            with pytest.raises(SystemExit) as exc_info:
                runpy.run_module("run_handler", run_name="__main__")

        assert exc_info.value.code == 1
