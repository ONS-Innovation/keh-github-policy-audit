"""Unit tests for dependabot_slo organisation check handler."""

import importlib
import json
from unittest.mock import Mock, create_autospec, patch

module = importlib.import_module("functions.organisation_checks.dependabot_slo.handler")


class TestDependabotSloHandler:
    def test_passes_repository_names_from_local_file(
        self, monkeypatch, tmp_path
    ) -> None:
        """The handler should load repository names from the local audit run."""
        monkeypatch.setenv("ENVIRONMENT", "local")
        monkeypatch.chdir(tmp_path)
        repository_list = (
            tmp_path
            / "outputs"
            / "audit-runs"
            / "ONS-Innovation"
            / "run-1"
            / "repositories-list.json"
        )
        repository_list.parent.mkdir(parents=True)
        repository_list.write_text(json.dumps([{"name": "active-repo"}]))
        captured: dict[str, object] = {}

        def fake_check(check_client, levels, repository_names):
            captured.update(
                client=check_client, levels=levels, repository_names=repository_names
            )
            return {"status": "PASS"}

        with (
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(module, "get_dependabot_slo", side_effect=fake_check),
        ):
            module.handler({"owner": "ONS-Innovation", "run_id": "run-1"}, None)

        assert captured["repository_names"] == ["active-repo"]

    def test_passes_repository_names_from_s3_reference(self) -> None:
        """The handler should pass active repository names to the Methods library."""
        client = object()
        captured: dict[str, object] = {}

        def fake_check(check_client, levels, repository_names):
            captured.update(
                client=check_client, levels=levels, repository_names=repository_names
            )
            return {"status": "PASS"}

        mock_s3 = Mock()
        mock_s3.get_object.return_value = {
            "Body": Mock(
                read=Mock(return_value=json.dumps([{"name": "active-repo"}]).encode())
            )
        }
        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "boto3") as mock_boto3,
            patch.object(module, "get_dependabot_slo", side_effect=fake_check),
        ):
            mock_boto3.client.return_value = mock_s3
            result = module.handler(
                {
                    "owner": "ONS-Innovation",
                    "levels": ["critical"],
                    "repositories_s3_ref": {
                        "s3_bucket": "bucket",
                        "s3_key": "repositories.json",
                    },
                },
                None,
            )

        assert captured == {
            "client": client,
            "levels": ["critical"],
            "repository_names": ["active-repo"],
        }
        assert result == {"status": "PASS", "check_name": "dependabot_slo"}

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

        mock_check = create_autospec(module.get_dependabot_slo, side_effect=fake_check)

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

        mock_check = create_autospec(module.get_dependabot_slo, side_effect=fake_check)

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(module, "get_dependabot_slo", mock_check),
        ):
            result = module.handler({"owner": "ONS-Innovation"}, None)

        assert captured == {"client": client, "levels": None}
        assert result == {"status": "PASS", "check_name": "dependabot_slo"}
