"""Unit tests for organisation teams listing handler."""

import importlib
import os
from unittest.mock import create_autospec, patch

import pytest


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


class TestListTeamsHandler:
    module = importlib.import_module("functions.list_teams.handler")

    def test_fetches_paginated_teams_and_writes_to_s3(self) -> None:
        """The handler should fetch teams, write to S3, and return S3 reference + teams list."""
        client = object()
        captured: dict[str, object] = {}

        def fake_get_paginated_list(
            check_client: object,
            endpoint: str,
            result_key: str,
        ) -> list[dict[str, str]]:
            captured["client"] = check_client
            captured["endpoint"] = endpoint
            captured["result_key"] = result_key
            return [{"slug": "keh-dev", "name": "KEH Developers"}]

        mock_paginated = create_autospec(
            self.module.get_paginated_list, side_effect=fake_get_paginated_list
        )

        with (
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}),
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "get_paginated_list", mock_paginated),
            patch("boto3.client") as mock_boto3,
        ):
            mock_s3_client = mock_boto3.return_value
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
            "endpoint": "/orgs/ONS-Innovation/teams?per_page=100",
            "result_key": "teams",
        }

        # Verify S3 write was called
        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert (
            call_kwargs["Key"]
            == "audit-runs/ONS-Innovation/test-run-123/teams-list.json"
        )

        # Verify response includes S3 reference (but not inline teams list)
        assert result["s3_bucket"] == "test-bucket"
        assert (
            result["s3_key"] == "audit-runs/ONS-Innovation/test-run-123/teams-list.json"
        )
        assert result["team_count"] == 1
        assert "teams" not in result  # Teams no longer included in response
        assert result["environment"] == "prod"

    def test_raises_for_missing_owner(self) -> None:
        """A missing owner key in the event should raise a KeyError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            with pytest.raises(KeyError, match="owner"):
                self.module.handler(
                    {"run_id": "test-run", "output_bucket": "bucket"},
                    None,
                )

    def test_uses_default_run_id_when_missing(self) -> None:
        """A missing run_id should use 'default-run' as fallback."""
        client = object()
        mock_paginated = create_autospec(
            self.module.get_paginated_list,
            return_value=[{"slug": "team-a", "name": "Team A"}],
        )

        with (
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}),
            patch("utils.github.get_github_client", return_value=client),
            patch.object(self.module, "get_paginated_list", mock_paginated),
            patch("boto3.client"),
        ):
            result = self.module.handler(
                {"owner": "ONS-Innovation", "output_bucket": "bucket"},
                None,
            )

        assert (
            result["s3_key"] == "audit-runs/ONS-Innovation/default-run/teams-list.json"
        )

    def test_raises_for_non_list_non_dict_payload(self) -> None:
        """A payload that is neither a list nor a dict should raise a clear type error."""
        with (
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}),
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(
                self.module,
                "get_paginated_list",
                return_value=42,
            ),
            patch("boto3.client"),
            pytest.raises(
                TypeError,
                match="got int",
            ),
        ):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "run_id": "test-run",
                    "output_bucket": "bucket",
                },
                None,
            )

    def test_raises_for_error_dict_payload(self) -> None:
        """A dict payload from pagination should fail with a clear type error."""
        with (
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}),
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(
                self.module,
                "get_paginated_list",
                return_value={"error": "rate limit", "response": {}},
            ),
            patch("boto3.client"),
            pytest.raises(
                TypeError,
                match="Expected teams payload to be a list of objects",
            ),
        ):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "run_id": "test-run",
                    "output_bucket": "bucket",
                },
                None,
            )

    def test_raises_for_non_object_item_in_payload(self) -> None:
        """A payload item that is not a dict should fail with a clear type error."""
        with (
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}),
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(
                self.module,
                "get_paginated_list",
                return_value=["not-a-team-object"],
            ),
            patch("boto3.client"),
            pytest.raises(
                TypeError,
                match="Expected teams payload to contain only objects",
            ),
        ):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "run_id": "test-run",
                    "output_bucket": "bucket",
                },
                None,
            )

    def test_raises_for_invalid_environment(self) -> None:
        """An invalid ENVIRONMENT value should raise a ValueError."""
        with (
            patch.dict(os.environ, {"ENVIRONMENT": "staging"}),
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(
                self.module,
                "get_paginated_list",
                return_value=[{"slug": "team-a", "name": "Team A"}],
            ),
            pytest.raises(
                ValueError,
                match="ENVIRONMENT must be either 'local' or 'prod'",
            ),
        ):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "run_id": "test-run",
                    "output_bucket": "bucket",
                },
                None,
            )

    def test_raises_for_missing_bucket_in_prod(self) -> None:
        """Missing bucket_name in prod environment should raise a ValueError."""
        with (
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=True),
            patch("utils.github.get_github_client", return_value=object()),
            patch.object(
                self.module,
                "get_paginated_list",
                return_value=[{"slug": "team-a", "name": "Team A"}],
            ),
            pytest.raises(
                ValueError,
                match="output_bucket \\(or S3_BUCKET_NAME\\) is required in prod",
            ),
        ):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "run_id": "test-run",
                },
                None,
            )

    def test_writes_teams_to_local_file_in_local_environment(self) -> None:
        """In local environment, teams should be written to local file system."""
        import json
        import tempfile

        client = object()
        mock_paginated = create_autospec(
            self.module.get_paginated_list,
            return_value=[
                {"slug": "team-a", "name": "Team A"},
                {"slug": "team-b", "name": "Team B"},
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with (
                    patch.dict(os.environ, {"ENVIRONMENT": "local"}, clear=True),
                    patch("utils.github.get_github_client", return_value=client),
                    patch.object(self.module, "get_paginated_list", mock_paginated),
                ):
                    result = self.module.handler(
                        {
                            "owner": "ONS-Innovation",
                            "run_id": "test-run-123",
                        },
                        None,
                    )

                # Verify file was written
                output_path = os.path.join(
                    tmpdir,
                    "outputs",
                    "audit-runs",
                    "ONS-Innovation",
                    "test-run-123",
                    "teams-list.json",
                )
                assert os.path.exists(output_path)

                with open(output_path, "r", encoding="utf-8") as f:
                    teams_data = json.load(f)

                assert teams_data == [
                    {"slug": "team-a", "name": "Team A"},
                    {"slug": "team-b", "name": "Team B"},
                ]

                assert result["environment"] == "local"
                assert result["team_count"] == 2
                assert result["s3_bucket"] is None
            finally:
                os.chdir(original_cwd)
