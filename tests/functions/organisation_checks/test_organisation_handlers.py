"""Unit tests for organisation-scoped Lambda check handlers."""

import importlib
from unittest.mock import create_autospec, patch


# ---------------------------------------------------------------------------
# dependabot_slo
# ---------------------------------------------------------------------------


class TestDependabotSloHandler:
    module = importlib.import_module(
        "functions.organisation_checks.dependabot_slo.handler"
    )

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
            self.module.get_dependabot_slo, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "get_dependabot_slo", mock_check),
        ):
            result = self.module.handler(
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
            self.module.get_dependabot_slo, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "get_dependabot_slo", mock_check),
        ):
            result = self.module.handler({"owner": "ONS-Innovation"}, None)

        assert captured == {"client": client, "levels": None}
        assert result == {"status": "PASS", "check_name": "dependabot_slo"}


# ---------------------------------------------------------------------------
# secret_scanning_slo
# ---------------------------------------------------------------------------


class TestSecretScanningSloHandler:
    module = importlib.import_module(
        "functions.organisation_checks.secret_scanning_slo.handler"
    )

    def test_wires_client(self) -> None:
        """The handler should wire the GitHub client to the check function."""
        client = object()
        captured: dict[str, object] = {}

        def fake_check(check_client: object) -> dict[str, object]:
            captured["client"] = check_client
            return {"status": "PASS"}

        mock_check = create_autospec(
            self.module.get_secret_scanning_slo, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "get_secret_scanning_slo", mock_check),
        ):
            result = self.module.handler({"owner": "ONS-Innovation"}, None)

        assert captured == {"client": client}
        assert result == {"status": "PASS", "check_name": "secret_scanning_slo"}


# ---------------------------------------------------------------------------
# team_maintainer
# ---------------------------------------------------------------------------


class TestTeamMaintainerHandler:
    module = importlib.import_module(
        "functions.organisation_checks.team_maintainer.handler"
    )

    def test_wires_team_slug(self) -> None:
        """The handler should wire the team_slug from the event to the check function."""
        client = object()
        captured: dict[str, object] = {}

        def fake_check(check_client: object, team_slug: str) -> dict[str, object]:
            captured["client"] = check_client
            captured["team_slug"] = team_slug
            return {"status": "PASS"}

        mock_check = create_autospec(
            self.module.check_team_maintainer, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "check_team_maintainer", mock_check),
        ):
            result = self.module.handler(
                {"owner": "ONS-Innovation", "team_slug": "keh-dev"}, None
            )

        assert captured == {"client": client, "team_slug": "keh-dev"}
        assert result == {"status": "PASS", "check_name": "team_maintainer"}
