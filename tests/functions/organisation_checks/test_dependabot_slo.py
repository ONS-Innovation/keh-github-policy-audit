"""Unit tests for dependabot_slo organisation check handler."""

import importlib
from unittest.mock import create_autospec, patch

module = importlib.import_module(
    "functions.organisation_checks.dependabot_slo.handler"
)


class TestDependabotSloHandler:
    def test_passes_levels(self) -> None:
        """The handler should forward the levels list to the check function."""
        client = object()
        captured: dict[str, object] = {}

        def fake_check(
            check_client: object, levels: list[str] | None
        ) -> dict[str, object]:
            captured["client"] = check_client
            captured["levels"] = levels
            return {"status": "PASS"}

        mock_check = create_autospec(
            module.get_dependabot_slo, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "get_dependabot_slo", mock_check),
        ):
            result = module.handler(
                {"owner": "ONS-Innovation", "levels": ["critical", "high"]}, None
            )

        assert captured == {"client": client, "levels": ["critical", "high"]}
        assert result == {"status": "PASS", "check_name": "dependabot_slo"}

    def test_defaults_levels_to_none(self) -> None:
        """The handler should default levels to None when not provided in the event."""
        client = object()
        captured: dict[str, object] = {}

        def fake_check(
            check_client: object, levels: list[str] | None
        ) -> dict[str, object]:
            captured["client"] = check_client
            captured["levels"] = levels
            return {"status": "PASS"}

        mock_check = create_autospec(
            module.get_dependabot_slo, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "get_dependabot_slo", mock_check),
        ):
            result = module.handler({"owner": "ONS-Innovation"}, None)

        assert captured == {"client": client, "levels": None}
        assert result == {"status": "PASS", "check_name": "dependabot_slo"}
