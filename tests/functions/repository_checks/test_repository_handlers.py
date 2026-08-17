"""Unit tests for repository-scoped Lambda check handlers."""

import importlib
from unittest.mock import create_autospec, patch

import pytest
from policy_methods_library.github.clients import GitHubRestClient

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
                patch("utils.github.get_github_client", return_value=client),
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

    def test_raises_when_result_is_error(self) -> None:
        """Handlers should fail fast when the policy library returns result=error."""
        for module_name, check_fn_name, check_name in REPO_CHECK_CASES:
            module = importlib.import_module(module_name)
            client = object()

            mock_check = create_autospec(
                getattr(module, check_fn_name),
                return_value={"result": "error", "message": "boom"},
            )

            with (
                patch("utils.github.get_github_client", return_value=client),
                patch.object(module, check_fn_name, mock_check),
                pytest.raises(RuntimeError, match=check_name),
            ):
                module.handler(
                    {
                        "owner": "ONS-Innovation",
                        "repository_name": "keh-github-policy-audit",
                    },
                    None,
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
            patch("utils.github.get_github_client", return_value=client),
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
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "check_inactivity", mock_check),
        ):
            result = self.module.handler(event, None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "data": None,
        }
        assert result == {"status": "PASS", "check_name": "inactivity"}

    def test_raises_when_result_is_error(self) -> None:
        """The handler should raise when the policy method returns an error result."""
        client = object()
        event = {
            "owner": "ONS-Innovation",
            "repository_name": "keh-github-policy-audit",
        }

        mock_check = create_autospec(
            self.module.check_inactivity,
            return_value={"result": "error", "message": "boom"},
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "check_inactivity", mock_check),
            pytest.raises(RuntimeError, match="inactivity"),
        ):
            self.module.handler(event, None)


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
            patch("utils.github.get_github_client", return_value=client),
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
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "check_security_scanning", mock_check),
        ):
            result = self.module.handler(event, None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "data": None,
        }
        assert result == {"status": "PASS", "check_name": "security_scanning"}

    def test_raises_when_result_is_error(self) -> None:
        """The handler should raise when the policy method returns an error result."""
        client = object()
        event = {
            "owner": "ONS-Innovation",
            "repository_name": "keh-github-policy-audit",
        }

        mock_check = create_autospec(
            self.module.check_security_scanning,
            return_value={"result": "error", "message": "boom"},
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "check_security_scanning", mock_check),
            pytest.raises(RuntimeError, match="security_scanning"),
        ):
            self.module.handler(event, None)


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

    def test_raises_when_result_is_error(self) -> None:
        """The handler should raise when the policy method returns an error result."""
        with (
            patch.object(
                self.module,
                "check_naming_convention",
                return_value={"result": "error", "message": "boom"},
            ),
            pytest.raises(RuntimeError, match="naming_convention"),
        ):
            self.module.handler({"repository_name": "keh-github-policy-audit"}, None)


# ---------------------------------------------------------------------------
# branch_protection handler
# ---------------------------------------------------------------------------


class TestBranchProtectionHandler:
    module = importlib.import_module(
        "functions.repository_checks.branch_protection.handler"
    )

    def _make_client(self, branch_names: list[str]) -> GitHubRestClient:
        """Return a mock GitHub client whose make_request returns the given branch list."""
        client = create_autospec(GitHubRestClient, instance=True)
        client.make_request.return_value.json.return_value = [
            {"name": name} for name in branch_names
        ]
        return client

    def test_selects_main_branch(self) -> None:
        """When 'main' is present it should be passed as the branch name."""
        client = self._make_client(["feature", "main", "master"])
        captured: dict[str, object] = {}

        def fake_check(
            c: object, repository_name: str, branch_name: str | None
        ) -> dict[str, object]:
            captured["client"] = c
            captured["repository_name"] = repository_name
            captured["branch_name"] = branch_name
            return {"status": "PASS"}

        mock_check = create_autospec(
            self.module.check_branch_protection, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "check_branch_protection", mock_check),
        ):
            result = self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "repository_name": "keh-github-policy-audit",
                },
                None,
            )

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "branch_name": "main",
        }
        assert result == {"status": "PASS", "check_name": "branch_protection"}

    def test_selects_master_branch_when_no_main(self) -> None:
        """When 'main' is absent but 'master' is present it should be passed as the branch name."""
        client = self._make_client(["master", "develop"])
        captured: dict[str, object] = {}

        def fake_check(
            c: object, repository_name: str, branch_name: str | None
        ) -> dict[str, object]:
            captured["branch_name"] = branch_name
            return {"status": "PASS"}

        mock_check = create_autospec(
            self.module.check_branch_protection, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "check_branch_protection", mock_check),
        ):
            result = self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "repository_name": "keh-github-policy-audit",
                },
                None,
            )

        assert captured["branch_name"] == "master"
        assert result == {"status": "PASS", "check_name": "branch_protection"}

    def test_passes_none_when_no_default_branch(self) -> None:
        """When neither 'main' nor 'master' exists the branch name should be None."""
        client = self._make_client(["develop", "feature"])
        captured: dict[str, object] = {}

        def fake_check(
            c: object, repository_name: str, branch_name: str | None
        ) -> dict[str, object]:
            captured["branch_name"] = branch_name
            return {"status": "PASS"}

        mock_check = create_autospec(
            self.module.check_branch_protection, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "check_branch_protection", mock_check),
        ):
            result = self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "repository_name": "keh-github-policy-audit",
                },
                None,
            )

        assert captured["branch_name"] is None
        assert result == {"status": "PASS", "check_name": "branch_protection"}

    def test_requests_correct_branches_endpoint(self) -> None:
        """The handler should call the branches endpoint for the correct owner and repo."""
        client = self._make_client([])

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(
                self.module,
                "check_branch_protection",
                return_value={"status": "PASS"},
            ),
        ):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "repository_name": "keh-github-policy-audit",
                },
                None,
            )

        client.make_request.assert_called_once_with(
            "GET", "/repos/ONS-Innovation/keh-github-policy-audit/branches"
        )

    def test_raises_for_missing_owner(self) -> None:
        """A missing owner key in the event should raise a KeyError."""
        with pytest.raises(KeyError, match="owner"):
            self.module.handler({"repository_name": "keh-github-policy-audit"}, None)

    def test_raises_for_missing_repository_name(self) -> None:
        """A missing repository_name key in the event should raise a KeyError."""
        with (
            patch(
                "utils.github.get_github_client",
                return_value=create_autospec(GitHubRestClient, instance=True),
            ),
            pytest.raises(KeyError, match="repository_name"),
        ):
            self.module.handler({"owner": "ONS-Innovation"}, None)

    def test_raises_when_result_is_error(self) -> None:
        """The handler should raise when the policy method returns an error result."""
        client = self._make_client(["main"])

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(
                self.module,
                "check_branch_protection",
                return_value={"result": "error", "message": "boom"},
            ),
            pytest.raises(RuntimeError, match="branch_protection"),
        ):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "repository_name": "keh-github-policy-audit",
                },
                None,
            )


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
