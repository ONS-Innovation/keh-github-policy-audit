"""Unit tests for repository-scoped Lambda check handlers."""

import importlib
from unittest.mock import create_autospec, patch

import pytest

REPO_CHECK_CASES = [
    (
        "functions.repository_checks.codeowners.handler",
        "check_codeowners",
        "codeowners",
    ),
    (
        "functions.repository_checks.dependabot.handler",
        "check_dependabot",
        "dependabot",
    ),
    (
        "functions.repository_checks.external_pull_request.handler",
        "check_external_pull_request",
        "external_pull_request",
    ),
    (
        "functions.repository_checks.gitignore.handler",
        "check_gitignore",
        "gitignore",
    ),
    (
        "functions.repository_checks.license.handler",
        "check_license",
        "license",
    ),
    (
        "functions.repository_checks.pirr.handler",
        "check_pirr",
        "pirr",
    ),
    (
        "functions.repository_checks.readme.handler",
        "check_readme",
        "readme",
    ),
    (
        "functions.repository_checks.repository_access.handler",
        "check_repository_access",
        "repository_access",
    ),
]


# ---------------------------------------------------------------------------
# standard repository-scoped handlers
# ---------------------------------------------------------------------------


class TestRepositoryScopedHandlers:
    def test_wire_client_and_repo(self) -> None:
        """All standard repository-scoped handlers should wire the client and repository name."""
        for module_name, check_fn_name, check_name in REPO_CHECK_CASES:
            module = importlib.import_module(module_name)
            client = object()
            captured: dict[str, object] = {}

            def fake_check(
                c: object, repository_name: str, _client=client, _captured=captured
            ) -> dict[str, object]:
                _captured["client"] = c
                _captured["repository_name"] = repository_name
                return {"status": "PASS"}

            mock_check = create_autospec(
                getattr(module, check_fn_name), side_effect=fake_check
            )

            with (
                patch.object(module, "get_github_client", return_value=client),
                patch.object(module, check_fn_name, mock_check),
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
            }, f"Failed for {module_name}"
            assert result == {"status": "PASS", "check_name": check_name}, (
                f"Failed for {module_name}"
            )


# ---------------------------------------------------------------------------
# inactivity handler
# ---------------------------------------------------------------------------


class TestInactivityHandler:
    module = importlib.import_module("functions.repository_checks.inactivity.handler")

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
            self.module.check_inactivity, side_effect=fake_check
        )

        with (
            patch.object(self.module, "get_github_client", return_value=client),
            patch.object(self.module, "check_inactivity", mock_check),
        ):
            result = self.module.handler(event, None)

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
            self.module.check_inactivity, side_effect=fake_check
        )

        with (
            patch.object(self.module, "get_github_client", return_value=client),
            patch.object(self.module, "check_inactivity", mock_check),
        ):
            result = self.module.handler(event, None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "data": None,
        }
        assert result == {"status": "PASS", "check_name": "inactivity"}


# ---------------------------------------------------------------------------
# security_scanning handler
# ---------------------------------------------------------------------------


class TestSecurityScanningHandler:
    module = importlib.import_module(
        "functions.repository_checks.security_scanning.handler"
    )

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
            self.module.check_security_scanning, side_effect=fake_check
        )

        with (
            patch.object(self.module, "get_github_client", return_value=client),
            patch.object(self.module, "check_security_scanning", mock_check),
        ):
            result = self.module.handler(event, None)

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
            self.module.check_security_scanning, side_effect=fake_check
        )

        with (
            patch.object(self.module, "get_github_client", return_value=client),
            patch.object(self.module, "check_security_scanning", mock_check),
        ):
            result = self.module.handler(event, None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "data": None,
        }
        assert result == {"status": "PASS", "check_name": "security_scanning"}


# ---------------------------------------------------------------------------
# naming_convention handler
# ---------------------------------------------------------------------------


class TestNamingConventionHandler:
    module = importlib.import_module(
        "functions.repository_checks.naming_convention.handler"
    )

    def test_uses_repository_name_only(self) -> None:
        """The handler should pass only the repository name (no client) to the check function."""
        captured: dict[str, object] = {}

        def fake_check(repository_name: str) -> dict[str, object]:
            captured["repository_name"] = repository_name
            return {"status": "PASS"}

        mock_check = create_autospec(
            self.module.check_naming_convention, side_effect=fake_check
        )

        with patch.object(self.module, "check_naming_convention", mock_check):
            result = self.module.handler(
                {"repository_name": "keh-github-policy-audit"}, None
            )

        assert captured == {"repository_name": "keh-github-policy-audit"}
        assert result == {"status": "PASS", "check_name": "naming_convention"}

    def test_raises_for_missing_repository_name(self) -> None:
        """A missing repository_name key in the event should raise a KeyError."""
        with pytest.raises(KeyError, match="repository_name"):
            self.module.handler({}, None)


# ---------------------------------------------------------------------------
# input validation
# ---------------------------------------------------------------------------


class TestCodeownersHandlerValidation:
    def test_raises_for_missing_owner(self) -> None:
        """A missing owner key in the event should raise a KeyError."""
        module = importlib.import_module(
            "functions.repository_checks.codeowners.handler"
        )
        with pytest.raises(KeyError, match="owner"):
            module.handler({"repository_name": "keh-github-policy-audit"}, None)
