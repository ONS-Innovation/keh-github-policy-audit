"""Unit tests for branch_protection repository check handler."""

import importlib
from unittest.mock import create_autospec, patch

import pytest
from policy_methods_library.github.clients import GitHubRestClient

module = importlib.import_module(
    "functions.repository_checks.branch_protection.handler"
)


class TestBranchProtectionHandler:
    def _make_event(self, default_branch: str | None) -> dict:
        return {
            "owner": "ONS-Innovation",
            "repository_name": "keh-github-policy-audit",
            "data": {"default_branch": default_branch},
        }

    def test_passes_default_branch_from_event_data(self) -> None:
        """The default_branch from event data should be passed directly to check_branch_protection."""
        client = create_autospec(GitHubRestClient, instance=True)
        captured: dict[str, object] = {}

        def fake_check(
            c: object, repository_name: str, branch_name: str | None
        ) -> dict[str, object]:
            captured["client"] = c
            captured["repository_name"] = repository_name
            captured["branch_name"] = branch_name
            return {"status": "PASS"}

        mock_check = create_autospec(
            module.check_branch_protection, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_branch_protection", mock_check),
        ):
            result = module.handler(self._make_event("main"), None)

        assert captured == {
            "client": client,
            "repository_name": "keh-github-policy-audit",
            "branch_name": "main",
        }
        assert result == {"status": "PASS", "check_name": "branch_protection"}

    def test_passes_non_standard_default_branch(self) -> None:
        """Any default_branch value should be forwarded, not just 'main' or 'master'."""
        client = create_autospec(GitHubRestClient, instance=True)
        captured: dict[str, object] = {}

        def fake_check(
            c: object, repository_name: str, branch_name: str | None
        ) -> dict[str, object]:
            captured["branch_name"] = branch_name
            return {"status": "PASS"}

        mock_check = create_autospec(
            module.check_branch_protection, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_branch_protection", mock_check),
        ):
            result = module.handler(self._make_event("develop"), None)

        assert captured["branch_name"] == "develop"
        assert result == {"status": "PASS", "check_name": "branch_protection"}

    def test_passes_none_when_default_branch_is_none(self) -> None:
        """A null default_branch in event data should be forwarded as None."""
        client = create_autospec(GitHubRestClient, instance=True)
        captured: dict[str, object] = {}

        def fake_check(
            c: object, repository_name: str, branch_name: str | None
        ) -> dict[str, object]:
            captured["branch_name"] = branch_name
            return {"status": "PASS"}

        mock_check = create_autospec(
            module.check_branch_protection, side_effect=fake_check
        )

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "check_branch_protection", mock_check),
        ):
            result = module.handler(self._make_event(None), None)

        assert captured["branch_name"] is None
        assert result == {"status": "PASS", "check_name": "branch_protection"}

    def test_does_not_call_branches_api(self) -> None:
        """The handler must not make any GitHub API calls to resolve the branch name."""
        client = create_autospec(GitHubRestClient, instance=True)

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(
                module,
                "check_branch_protection",
                return_value={"status": "PASS"},
            ),
        ):
            module.handler(self._make_event("main"), None)

        client.make_request.assert_not_called()

    def test_raises_for_missing_owner(self) -> None:
        """A missing owner key in the event should raise a KeyError."""
        with pytest.raises(KeyError, match="owner"):
            module.handler(
                {
                    "repository_name": "keh-github-policy-audit",
                    "data": {"default_branch": "main"},
                },
                None,
            )

    def test_raises_for_missing_repository_name(self) -> None:
        """A missing repository_name key in the event should raise a KeyError."""
        with (
            patch(
                "utils.github.get_github_client",
                return_value=create_autospec(GitHubRestClient, instance=True),
            ),
            pytest.raises(KeyError, match="repository_name"),
        ):
            module.handler(
                {"owner": "ONS-Innovation", "data": {"default_branch": "main"}}, None
            )
