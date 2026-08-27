"""Unit tests for store_organisation_checks Lambda handler."""

import importlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestStoreOrganisationChecksValidation:
    module = importlib.import_module(
        "functions.storage_functions.store_organisation_checks.handler"
    )

    def test_requires_owner(self) -> None:
        with pytest.raises(KeyError):
            self.module.handler(
                {
                    "run_id": "run-1",
                    "check_name": "dependabot_slo",
                    "result": "pass",
                },
                None,
            )

    def test_requires_run_id(self) -> None:
        with pytest.raises(KeyError):
            self.module.handler(
                {
                    "owner": "test-org",
                    "check_name": "dependabot_slo",
                    "result": "pass",
                },
                None,
            )

    def test_requires_check_name(self) -> None:
        with pytest.raises(KeyError):
            self.module.handler(
                {
                    "owner": "test-org",
                    "run_id": "run-1",
                    "result": "pass",
                },
                None,
            )

    def test_raises_for_invalid_environment(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            with pytest.raises(ValueError, match="ENVIRONMENT"):
                self.module.handler(
                    {
                        "owner": "test-org",
                        "run_id": "run-1",
                        "check_name": "dependabot_slo",
                        "result": "pass",
                        "message": "Dependabot meets SLO",
                        "details": {},
                    },
                    None,
                )

    def test_raises_in_prod_when_bucket_missing(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=True):
            with pytest.raises(ValueError, match="output_bucket"):
                self.module.handler(
                    {
                        "owner": "test-org",
                        "run_id": "run-1",
                        "check_name": "dependabot_slo",
                        "result": "pass",
                        "message": "Dependabot meets SLO",
                        "details": {},
                    },
                    None,
                )


class TestStoreOrganisationChecksLocal:
    module = importlib.import_module(
        "functions.storage_functions.store_organisation_checks.handler"
    )

    def setup_method(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp_dir.name)
        self._original_cwd = os.getcwd()
        os.chdir(self.tmp_path)

    def teardown_method(self) -> None:
        os.chdir(self._original_cwd)
        self._tmp_dir.cleanup()

    def test_defaults_to_local_environment(self) -> None:
        """When ENVIRONMENT is not set, defaults to 'local' and writes to filesystem."""
        with patch.dict(os.environ, {}, clear=True):
            result = self.module.handler(
                {
                    "owner": "test-org",
                    "run_id": "run-1",
                    "check_name": "dependabot_slo",
                    "result": "pass",
                    "message": "Dependabot meets SLO",
                    "details": {},
                },
                None,
            )

        assert result["status"] == "success"
        assert result["check_name"] == "dependabot_slo"

        # Verify file was written
        output_path = Path(result["local_output_path"])
        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)
        assert data["owner"] == "test-org"
        assert data["check_name"] == "dependabot_slo"
        assert data["result"] == "pass"
        assert data["message"] == "Dependabot meets SLO"

    def test_returns_s3_reference_in_prod(self) -> None:
        """In prod environment, should write to S3 and return S3 reference."""
        with (
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}),
            patch("boto3.client") as mock_boto3,
        ):
            mock_s3_client = mock_boto3.return_value
            result = self.module.handler(
                {
                    "owner": "test-org",
                    "run_id": "run-1",
                    "output_bucket": "test-bucket",
                    "check_name": "dependabot_slo",
                    "result": "pass",
                    "message": "Dependabot meets SLO",
                    "details": {"total_open_alerts": 100},
                },
                None,
            )

        assert result["status"] == "success"
        assert result["bucket"] == "test-bucket"
        assert (
            result["key"]
            == "audit-runs/test-org/run-1/organisation-checks/dependabot_slo.json"
        )

        # Verify S3 write was called
        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert (
            call_kwargs["Key"]
            == "audit-runs/test-org/run-1/organisation-checks/dependabot_slo.json"
        )

    def test_stores_details_in_output(self) -> None:
        """Details should be included in the stored output."""
        with patch.dict(os.environ, {}, clear=True):
            details = {
                "total_open_alerts": 374,
                "repositories_affected": 23,
            }
            result = self.module.handler(
                {
                    "owner": "test-org",
                    "run_id": "run-1",
                    "check_name": "dependabot_slo",
                    "result": "fail",
                    "message": "Too many open alerts",
                    "details": details,
                },
                None,
            )

        output_path = Path(result["local_output_path"])
        with open(output_path) as f:
            data = json.load(f)
        assert data["details"] == details
