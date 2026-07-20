"""Unit tests for loading repositories from S3."""

import importlib
import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


class TestLoadRepositoriesHandler:
    module = importlib.import_module("functions.load_repositories.handler")

    def test_loads_repositories_from_s3(self) -> None:
        """The handler should load repositories from S3 and return the list."""
        test_repositories = [
            {
                "name": "repo-1",
                "data": {
                    "updated_at": "2024-01-01T00:00:00Z",
                    "visibility": "public",
                    "security_and_analysis": {"secret_scanning": {"status": "enabled"}},
                },
            },
            {
                "name": "repo-2",
                "data": {
                    "updated_at": "2024-01-02T00:00:00Z",
                    "visibility": "private",
                    "security_and_analysis": None,
                },
            },
        ]

        s3_content = {
            "owner": "test-org",
            "run_id": "test-run-123",
            "repositories": test_repositories,
            "repository_count": 2,
            "timestamp": "2024-01-03T00:00:00Z",
        }

        mock_s3_client = MagicMock()
        mock_response = {
            "Body": MagicMock(
                read=MagicMock(return_value=json.dumps(s3_content).encode("utf-8"))
            )
        }
        mock_s3_client.get_object.return_value = mock_response

        with patch.object(self.module, "boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_s3_client
            result = self.module.handler(
                {
                    "s3_bucket": "test-bucket",
                    "s3_key": "audit-runs/test-org/test-run-123/repositories-list.json",
                },
                None,
            )

        assert result == test_repositories
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="audit-runs/test-org/test-run-123/repositories-list.json",
        )

    def test_raises_for_missing_s3_bucket(self) -> None:
        """A missing s3_bucket should raise ValueError."""
        with pytest.raises(ValueError, match="s3_bucket and s3_key are required"):
            self.module.handler(
                {
                    "s3_key": "audit-runs/test-org/test-run-123/repositories-list.json",
                },
                None,
            )

    def test_raises_for_missing_s3_key(self) -> None:
        """A missing s3_key should raise ValueError."""
        with pytest.raises(ValueError, match="s3_bucket and s3_key are required"):
            self.module.handler(
                {
                    "s3_bucket": "test-bucket",
                },
                None,
            )

    def test_handles_s3_errors_gracefully(self) -> None:
        """S3 errors should be logged and re-raised."""
        mock_s3_client = MagicMock()
        mock_s3_client.get_object.side_effect = Exception("S3 access denied")

        with (
            patch.object(self.module, "boto3") as mock_boto3,
            pytest.raises(Exception, match="S3 access denied"),
        ):
            mock_boto3.client.return_value = mock_s3_client
            self.module.handler(
                {
                    "s3_bucket": "test-bucket",
                    "s3_key": "audit-runs/test-org/test-run-123/repositories-list.json",
                },
                None,
            )
