"""Unit tests for inactivity repository check handler."""

import importlib
from unittest.mock import create_autospec, patch

module = importlib.import_module("functions.repository_checks.inactivity.handler")


class TestInactivityHandler:
    def test_passes_event_data_for_flat_payload(self) -> None:
        """The handler should forward the data dict from the event to the check function."""
        client = object()
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

        mock_check = create_autospec(
            module.check_inactivity, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_inactivity", mock_check),
        ):
            result = module.handler(event, None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "data": {"updated_at": "2026-07-03T10:00:00Z"},
        }
        assert result == {"status": "PASS", "check_name": "inactivity"}

    def test_passes_none_when_data_missing(self) -> None:
        """The handler should pass None as data when the event does not include a data key."""
        client = object()
        captured: dict[str, object] = {}
        event = {
            "owner": "ONS-Innovation",
            "repository_name": "keh-github-policy-audit",
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

        mock_check = create_autospec(
            module.check_inactivity, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_inactivity", mock_check),
        ):
            result = module.handler(event, None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "data": None,
        }
        assert result == {"status": "PASS", "check_name": "inactivity"}
