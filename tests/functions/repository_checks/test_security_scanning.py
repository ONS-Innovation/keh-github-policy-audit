"""Unit tests for security_scanning repository check handler."""

import importlib
from unittest.mock import create_autospec, patch

module = importlib.import_module(
    "functions.repository_checks.security_scanning.handler"
)


class TestSecurityScanningHandler:
    def test_passes_event_data_for_flat_payload(self) -> None:
        """The handler should forward the data dict from the event to the check function."""
        client = object()
        captured: dict[str, object] = {}
        event = {
            "owner": "ONS-Innovation",
            "repository_name": "keh-github-policy-audit",
            "data": {
                "security_and_analysis": {"secret_scanning": {"status": "enabled"}}
            },
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
            module.check_security_scanning, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_security_scanning", mock_check),
        ):
            result = module.handler(event, None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "data": {
                "security_and_analysis": {"secret_scanning": {"status": "enabled"}}
            },
        }
        assert result == {"status": "PASS", "check_name": "security_scanning"}

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
            module.check_security_scanning, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_security_scanning", mock_check),
        ):
            result = module.handler(event, None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "data": None,
        }
        assert result == {"status": "PASS", "check_name": "security_scanning"}
