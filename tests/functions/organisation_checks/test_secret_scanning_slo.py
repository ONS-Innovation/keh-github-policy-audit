"""Unit tests for secret_scanning_slo organisation check handler."""

import importlib
from unittest.mock import create_autospec, patch

module = importlib.import_module(
    "functions.organisation_checks.secret_scanning_slo.handler"
)


class TestSecretScanningSloHandler:
    def test_wires_client(self) -> None:
        """The handler should wire the GitHub client to the check function."""
        client = object()
        captured: dict[str, object] = {}

        def fake_check(check_client: object) -> dict[str, object]:
            captured["client"] = check_client
            return {"status": "PASS"}

        mock_check = create_autospec(
            module.get_secret_scanning_slo, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "get_secret_scanning_slo", mock_check),
        ):
            result = module.handler({"owner": "ONS-Innovation"}, None)

        assert captured == {"client": client}
        assert result == {"status": "PASS", "check_name": "secret_scanning_slo"}
