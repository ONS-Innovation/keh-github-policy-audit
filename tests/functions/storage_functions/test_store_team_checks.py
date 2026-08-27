"""Unit tests for store_team_checks Lambda handler."""

import importlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestStoreTeamChecksValidation:
    module = importlib.import_module(
        "functions.storage_functions.store_team_checks.handler"
    )

    def test_requires_owner(self) -> None:
        with pytest.raises(KeyError):
            self.module.handler(
                {
                    "run_id": "run-1",
                    "team_slug": "team-a",
                    "checks": [],
                },
                None,
            )

    def test_requires_run_id(self) -> None:
        with pytest.raises(KeyError):
            self.module.handler(
                {
                    "owner": "test-org",
                    "team_slug": "team-a",
                    "checks": [],
                },
                None,
            )

    def test_requires_team_slug(self) -> None:
        with pytest.raises(KeyError):
            self.module.handler(
                {
                    "owner": "test-org",
                    "run_id": "run-1",
                    "checks": [],
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
                        "team_slug": "team-a",
                        "checks": [
                            {
                                "check_name": "team_maintainer",
                                "result": "pass",
                                "message": "Team has maintainers",
                            }
                        ],
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
                        "team_slug": "team-a",
                        "checks": [
                            {
                                "check_name": "team_maintainer",
                                "result": "pass",
                                "message": "Team has maintainers",
                            }
                        ],
                    },
                    None,
                )


class TestStoreTeamChecksLocal:
    module = importlib.import_module(
        "functions.storage_functions.store_team_checks.handler"
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
                    "team_slug": "team-a",
                    "checks": [
                        {
                            "check_name": "team_maintainer",
                            "result": "pass",
                            "message": "Team has maintainers",
                        }
                    ],
                },
                None,
            )

        assert result["status"] == "success"
        assert result["environment"] == "local"
        assert result["team_slug"] == "team-a"
        assert result["checks_count"] == 1

        # Verify file was written
        output_path = Path(result["local_output_path"])
        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)
        assert data["owner"] == "test-org"
        assert data["team_slug"] == "team-a"
        assert "team_maintainer" in data["checks"]
        assert data["checks"]["team_maintainer"]["result"] == "pass"

    def test_handles_multiple_checks(self) -> None:
        """Multiple checks should be stored as a dictionary keyed by check_name."""
        with patch.dict(os.environ, {}, clear=True):
            result = self.module.handler(
                {
                    "owner": "test-org",
                    "run_id": "run-1",
                    "team_slug": "team-a",
                    "checks": [
                        {
                            "check_name": "team_maintainer",
                            "result": "pass",
                            "message": "Team has maintainers",
                        },
                        {
                            "check_name": "team_secret_scanning",
                            "result": "fail",
                            "message": "Secret scanning not enabled",
                        },
                    ],
                },
                None,
            )

        assert result["checks_count"] == 2

        output_path = Path(result["local_output_path"])
        with open(output_path) as f:
            data = json.load(f)
        assert len(data["checks"]) == 2
        assert data["checks"]["team_maintainer"]["result"] == "pass"
        assert data["checks"]["team_secret_scanning"]["result"] == "fail"

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
                    "team_slug": "team-a",
                    "output_bucket": "test-bucket",
                    "checks": [
                        {
                            "check_name": "team_maintainer",
                            "result": "pass",
                            "message": "Team has maintainers",
                        }
                    ],
                },
                None,
            )

        assert result["status"] == "success"
        assert result["environment"] == "prod"
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "audit-runs/test-org/run-1/teams/team-a.json"

        # Verify S3 put_object was called with correct parameters
        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "audit-runs/test-org/run-1/teams/team-a.json"


class TestNormaliseChecks:
    module = importlib.import_module(
        "functions.storage_functions.store_team_checks.handler"
    )

    def test_handles_checks_as_dict(self) -> None:
        """When checks is already a dict, should return it as-is."""
        checks_dict = {
            "team_maintainer": {"result": "pass"},
            "team_security": {"result": "fail"},
        }
        result = self.module._normalise_checks(checks_dict)
        assert result is checks_dict

    def test_handles_checks_as_list(self) -> None:
        """When checks is a list, should convert to dict keyed by check_name."""
        checks_list = [
            {"check_name": "team_maintainer", "result": "pass"},
            {"check_name": "team_security", "result": "fail"},
        ]
        result = self.module._normalise_checks(checks_list)
        assert result == {
            "team_maintainer": {"check_name": "team_maintainer", "result": "pass"},
            "team_security": {"check_name": "team_security", "result": "fail"},
        }

    def test_raises_for_invalid_checks_type(self) -> None:
        """When checks is neither dict nor list, should raise ValueError."""
        with pytest.raises(ValueError, match="'checks' must be a dictionary or list"):
            self.module._normalise_checks("invalid")

        with pytest.raises(ValueError, match="'checks' must be a dictionary or list"):
            self.module._normalise_checks(123)

        with pytest.raises(ValueError, match="'checks' must be a dictionary or list"):
            self.module._normalise_checks(None)

    def test_skips_non_dict_items_in_list(self) -> None:
        """When list contains non-dict items, should skip them."""
        checks_list = [
            {"check_name": "team_maintainer", "result": "pass"},
            "not a dict",  # Should be skipped
            123,  # Should be skipped
            None,  # Should be skipped
            {"check_name": "team_security", "result": "fail"},
        ]
        result = self.module._normalise_checks(checks_list)
        assert len(result) == 2
        assert "team_maintainer" in result
        assert "team_security" in result

    def test_skips_items_without_valid_check_name(self) -> None:
        """When dict in list has no/empty/non-string check_name, should skip it."""
        checks_list = [
            {"check_name": "team_maintainer", "result": "pass"},
            {"result": "fail"},  # Missing check_name
            {"check_name": None, "result": "fail"},  # None check_name
            {"check_name": "", "result": "fail"},  # Empty string check_name
            {"check_name": 123, "result": "fail"},  # Non-string check_name
            {"check_name": "team_security", "result": "fail"},
        ]
        result = self.module._normalise_checks(checks_list)
        assert len(result) == 2
        assert "team_maintainer" in result
        assert "team_security" in result
