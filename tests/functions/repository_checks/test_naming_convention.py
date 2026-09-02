"""Unit tests for naming_convention repository check handler."""

import importlib
from unittest.mock import create_autospec, patch

import pytest

module = importlib.import_module(
    "functions.repository_checks.naming_convention.handler"
)


class TestNamingConventionHandler:
    def test_uses_repository_name_only(self) -> None:
        """The handler should pass only the repository name (no client) to the check function."""
        captured: dict[str, object] = {}

        def fake_check(repository_name: str) -> dict[str, object]:
            captured["repository_name"] = repository_name
            return {"status": "PASS"}

        mock_check = create_autospec(
            module.check_naming_convention, side_effect=fake_check
        )

        with patch.object(module, "check_naming_convention", mock_check):
            result = module.handler(
                {"repository_name": "keh-github-policy-audit"}, None
            )

        assert captured == {"repository_name": "keh-github-policy-audit"}
        assert result == {"status": "PASS", "check_name": "naming_convention"}

    def test_raises_for_missing_repository_name(self) -> None:
        """A missing repository_name key in the event should raise a KeyError."""
        with pytest.raises(KeyError, match="repository_name"):
            module.handler({}, None)
