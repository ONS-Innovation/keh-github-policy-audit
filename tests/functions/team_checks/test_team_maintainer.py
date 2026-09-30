"""Unit tests for team_maintainer team check handler."""

import importlib
from unittest.mock import create_autospec, patch

module = importlib.import_module("functions.team_checks.team_maintainer.handler")


class TestTeamMaintainerHandler:
    def test_wires_team_slug(self) -> None:
        """The handler should wire the team_slug from the event to the check function."""
        client = object()
        captured: dict[str, object] = {}

        def fake_check(check_client: object, team_slug: str) -> dict[str, object]:
            captured["client"] = check_client
            captured["team_slug"] = team_slug
            return {"status": "PASS"}

        mock_check = create_autospec(
            module.check_team_maintainer, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_team_maintainer", mock_check),
        ):
            result = module.handler(
                {"owner": "ONS-Innovation", "team_slug": "keh-dev"}, None
            )

        assert captured == {"client": client, "team_slug": "keh-dev"}
        assert result == {"status": "PASS", "check_name": "team_maintainer"}
