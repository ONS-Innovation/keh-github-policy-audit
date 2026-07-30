"""Unit tests for repository listing handler."""

import importlib
import os
from unittest.mock import MagicMock, create_autospec, patch

import pytest


# ---------------------------------------------------------------------------
# _slim_security_and_analysis
# ---------------------------------------------------------------------------


class TestSlimSecurityAndAnalysis:
    module = importlib.import_module("functions.list_repositories.handler")

    def test_retains_only_status_per_feature(self) -> None:
        """Each feature should be reduced to {"status": ...}, dropping all other keys."""
        raw = {
            "secret_scanning": {"status": "enabled", "url": "https://example.com"},
            "secret_scanning_push_protection": {"status": "enabled"},
            "dependabot_security_updates": {"status": "disabled"},
            "secret_scanning_ai_detection": {"status": "disabled", "extra": "noise"},
        }
        result = self.module._slim_security_and_analysis(raw)
        assert result == {
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "enabled"},
            "dependabot_security_updates": {"status": "disabled"},
            "secret_scanning_ai_detection": {"status": "disabled"},
        }

    def test_drops_features_without_status(self) -> None:
        """Features that have no 'status' key should be excluded."""
        raw = {
            "secret_scanning": {"status": "enabled"},
            "broken_feature": {"url": "https://example.com"},
        }
        result = self.module._slim_security_and_analysis(raw)
        assert result == {"secret_scanning": {"status": "enabled"}}

    def test_returns_none_for_none_input(self) -> None:
        assert self.module._slim_security_and_analysis(None) is None

    def test_returns_input_unchanged_for_non_dict(self) -> None:
        assert self.module._slim_security_and_analysis("unexpected") == "unexpected"


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


class TestListRepositoriesHandler:
    module = importlib.import_module("functions.list_repositories.handler")

    def test_raises_for_invalid_environment(self) -> None:
        """An unsupported ENVIRONMENT value should raise ValueError."""
        with (
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(
                self.module,
                "get_paginated_list",
                return_value=[{"name": "keh-github-policy-audit"}],
            ),
            patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=False),
            pytest.raises(
                ValueError, match="ENVIRONMENT must be either 'local' or 'prod'"
            ),
        ):
            self.module.handler({"owner": "ONS-Innovation"}, None)

    def test_raises_for_missing_output_bucket_in_prod(self) -> None:
        """Prod execution requires either output_bucket or S3_BUCKET_NAME."""
        with (
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(
                self.module,
                "get_paginated_list",
                return_value=[{"name": "keh-github-policy-audit"}],
            ),
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=True),
            pytest.raises(
                ValueError,
                match=r"output_bucket \(or S3_BUCKET_NAME\) is required in prod",
            ),
        ):
            self.module.handler({"owner": "ONS-Innovation"}, None)

    def test_writes_repository_list_locally(self, tmp_path, monkeypatch) -> None:
        """Local execution should write the repository list to disk."""
        monkeypatch.chdir(tmp_path)

        with (
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(
                self.module,
                "get_paginated_list",
                return_value=[{"name": "keh-github-policy-audit"}],
            ),
            patch.dict(os.environ, {"ENVIRONMENT": "local"}, clear=True),
        ):
            result = self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "run_id": "test-run-123",
                },
                None,
            )

        assert result["environment"] == "local"
        assert result["s3_bucket"] is None
        assert result["local_output_path"] == os.path.join(
            "outputs", "ONS-Innovation", "test-run-123", "repositories-list.json"
        )

        with open(result["local_output_path"], encoding="utf-8") as output_file:
            stored_data = self.module.json.load(output_file)

        assert len(stored_data) == 1
        assert stored_data[0]["name"] == "keh-github-policy-audit"

    def test_fetches_paginated_repositories_and_writes_to_s3(self) -> None:
        """The handler should fetch repositories, write to S3, and return S3 reference."""
        client = object()
        captured: dict[str, object] = {}

        def fake_get_paginated_list(
            check_client: object,
            endpoint: str,
            result_key: str,
        ) -> list[dict[str, object]]:
            captured["client"] = check_client
            captured["endpoint"] = endpoint
            captured["result_key"] = result_key
            return [{"name": "keh-github-policy-audit"}]

        mock_paginated = create_autospec(
            self.module.get_paginated_list, side_effect=fake_get_paginated_list
        )
        mock_s3_client = MagicMock()

        with (
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "get_paginated_list", mock_paginated),
            patch.object(self.module, "boto3") as mock_boto3,
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=False),
        ):
            mock_boto3.client.return_value = mock_s3_client
            result = self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "run_id": "test-run-123",
                    "output_bucket": "test-bucket",
                },
                None,
            )

        assert captured == {
            "client": client,
            "endpoint": "/orgs/ONS-Innovation/repos?per_page=100",
            "result_key": "repositories",
        }

        # Verify S3 write was called
        assert mock_s3_client.put_object.called
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert "ONS-Innovation" in call_kwargs["Key"]
        assert "test-run-123" in call_kwargs["Key"]

        # Verify return structure
        assert result["s3_bucket"] == "test-bucket"
        assert result["repository_count"] == 1
        assert result["environment"] == "prod"
        assert "ONS-Innovation" in result["s3_key"]

    def test_raises_for_missing_owner(self) -> None:
        """A missing owner key in the event should raise a KeyError."""
        with pytest.raises(KeyError, match="owner"):
            self.module.handler(
                {
                    "run_id": "test-run",
                    "output_bucket": "test-bucket",
                },
                None,
            )

    def test_excludes_archived_repositories(self) -> None:
        """Archived repositories should not be written to S3."""
        repositories = [
            {"name": "active-repo", "archived": False},
            {"name": "archived-repo", "archived": True},
        ]
        mock_s3_client = MagicMock()

        with (
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(self.module, "get_paginated_list", return_value=repositories),
            patch.object(self.module, "boto3") as mock_boto3,
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=False),
        ):
            mock_boto3.client.return_value = mock_s3_client
            result = self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "run_id": "test-run-123",
                    "output_bucket": "test-bucket",
                },
                None,
            )

        assert result["repository_count"] == 1

        # Verify only active repo was stored
        call_kwargs = mock_s3_client.put_object.call_args[1]
        import json

        stored_data = json.loads(call_kwargs["Body"])
        assert len(stored_data) == 1
        assert stored_data[0]["name"] == "active-repo"
