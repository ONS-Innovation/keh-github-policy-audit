"""Unit tests for license repository check handler."""

import importlib
from unittest.mock import create_autospec, patch

module = importlib.import_module("functions.repository_checks.license.handler")


class TestLicenseHandler:
    def test_wire_client_and_repo(self) -> None:
        """The handler should wire the client and repository name to the check function."""
        client = object()
        captured: dict[str, object] = {}

        def fake_check(
            c: object, repository_name: str, _client=client, _captured=captured
        ) -> dict[str, object]:
            _captured["client"] = c
            _captured["repository_name"] = repository_name
            return {"status": "PASS"}

        mock_check = create_autospec(module.check_license, side_effect=fake_check)

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_license", mock_check),
        ):
            result = module.handler(
                {
                    "owner": "ONS-Innovation",
                    "repository_name": "keh-github-policy-audit",
                },
                None,
            )

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
        }
        assert result == {"status": "PASS", "check_name": "license"}
