"""Unit tests for codeowners repository check handler."""

import importlib
from unittest.mock import create_autospec, patch

import pytest

module = importlib.import_module("functions.repository_checks.codeowners.handler")


class TestCodeownersHandler:
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

        mock_check = create_autospec(
            module.check_codeowners, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_codeowners", mock_check),
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
        assert result == {"status": "PASS", "check_name": "codeowners"}


class TestCodeownersHandlerValidation:
    def test_raises_for_missing_owner(self) -> None:
        """A missing owner key in the event should raise a KeyError."""
        with pytest.raises(KeyError, match="owner"):
            module.handler({"repository_name": "keh-github-policy-audit"}, None)
