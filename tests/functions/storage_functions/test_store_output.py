"""Unit tests for store_output handler with parametrized tests."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch, MagicMock

import pytest

from functions.storage_functions.store_output.handler import (
    DataLoader,
    is_pass,
    normalise_organisation_checks,
    normalise_repository_checks,
    normalise_team_checks,
    build_summary,
    handler,
)


class TestDataLoader:
    """Test DataLoader functionality."""

    def test_local_environment_loads_from_local_files(
        self, tmp_path, monkeypatch
    ) -> None:
        """Local environment should load from local files instead of S3."""
        # Change working directory to tmp_path
        monkeypatch.chdir(tmp_path)

        # Create test directory structure
        org_dir = (
            tmp_path
            / "outputs"
            / "audit-runs"
            / "test-owner"
            / "test-run"
            / "organisation-checks"
        )
        org_dir.mkdir(parents=True)

        # Create test file
        test_file = org_dir / "test-check.json"
        test_file.write_text(json.dumps({"check_name": "test-check", "result": "pass"}))

        loader = DataLoader(environment="local", bucket_name=None, s3_client=None)
        result = loader.load_organisation_checks("test-owner", "test-run")

        assert "test-check" in result
        assert result["test-check"]["result"] == "pass"

    def test_local_environment_returns_empty_when_no_files(
        self, tmp_path, monkeypatch
    ) -> None:
        """Local environment should return empty dict when directory doesn't exist."""
        monkeypatch.chdir(tmp_path)

        loader = DataLoader(environment="local", bucket_name=None, s3_client=None)
        result = loader.load_organisation_checks("nonexistent", "nonexistent")

        assert result == {}

    def test_load_from_local_with_field_name_extraction(
        self, tmp_path, monkeypatch
    ) -> None:
        """Local loader should extract name from field_name in payload."""
        monkeypatch.chdir(tmp_path)

        repo_dir = (
            tmp_path / "outputs" / "audit-runs" / "owner" / "run-id" / "repositories"
        )
        repo_dir.mkdir(parents=True)

        # Create file with field_name in payload
        repo_file = repo_dir / "repo.json"
        repo_file.write_text(json.dumps({"repository_name": "my-repo", "checks": {}}))

        loader = DataLoader(environment="local", bucket_name=None, s3_client=None)
        result = loader.load_repository_checks("owner", "run-id")

        assert "my-repo" in result

    def test_load_from_local_falls_back_to_filename(
        self, tmp_path, monkeypatch
    ) -> None:
        """Local loader should fallback to filename when field_name not in payload."""
        monkeypatch.chdir(tmp_path)

        team_dir = tmp_path / "outputs" / "audit-runs" / "owner" / "run-id" / "teams"
        team_dir.mkdir(parents=True)

        # Create file without team_slug field
        team_file = team_dir / "my-team.json"
        team_file.write_text(json.dumps({"checks": []}))

        loader = DataLoader(environment="local", bucket_name=None, s3_client=None)
        result = loader.load_team_checks("owner", "run-id")

        # Should use filename as key
        assert "my-team" in result

    def test_load_from_local_skips_non_dict_payload(
        self, tmp_path, monkeypatch
    ) -> None:
        """Local loader should skip non-dict payloads."""
        monkeypatch.chdir(tmp_path)

        org_dir = (
            tmp_path
            / "outputs"
            / "audit-runs"
            / "owner"
            / "run-id"
            / "organisation-checks"
        )
        org_dir.mkdir(parents=True)

        # Create invalid JSON file
        invalid_file = org_dir / "invalid.json"
        invalid_file.write_text(json.dumps(["array"]))

        loader = DataLoader(environment="local", bucket_name=None, s3_client=None)
        result = loader.load_organisation_checks("owner", "run-id")

        assert result == {}

    def test_load_from_local_skips_malformed_json(self, tmp_path, monkeypatch) -> None:
        """Local loader should skip files with malformed JSON."""
        monkeypatch.chdir(tmp_path)

        org_dir = (
            tmp_path
            / "outputs"
            / "audit-runs"
            / "owner"
            / "run-id"
            / "organisation-checks"
        )
        org_dir.mkdir(parents=True)

        # Create malformed JSON file
        bad_file = org_dir / "bad.json"
        bad_file.write_text("not valid json {")

        loader = DataLoader(environment="local", bucket_name=None, s3_client=None)
        result = loader.load_organisation_checks("owner", "run-id")

        assert result == {}

    def test_load_from_local_handles_directory_read_errors(
        self, tmp_path, monkeypatch
    ) -> None:
        """Local loader should handle errors when reading directory."""
        monkeypatch.chdir(tmp_path)

        org_dir = (
            tmp_path
            / "outputs"
            / "audit-runs"
            / "owner"
            / "run-id"
            / "organisation-checks"
        )
        org_dir.mkdir(parents=True)

        # Create a file that will trigger an error
        test_file = org_dir / "test.json"
        test_file.write_text("{}")

        # Patch glob to raise an error
        with patch.object(Path, "glob", side_effect=OSError("Permission denied")):
            loader = DataLoader(environment="local", bucket_name=None, s3_client=None)
            result = loader.load_organisation_checks("owner", "run-id")

            assert result == {}

    def test_prod_environment_requires_bucket_and_s3_client(self) -> None:
        """Prod environment should require bucket_name and s3_client."""
        loader = DataLoader(environment="prod", bucket_name="my-bucket", s3_client=None)

        assert loader.environment == "prod"
        assert loader.bucket_name == "my-bucket"


@pytest.mark.parametrize(
    "method_name,prefix,field_name,log_context,key_example",
    [
        (
            "load_organisation_checks",
            "audit-runs/test-org/run-1/organisation-checks/",
            "check_name",
            "organisation_checks",
            "audit-runs/test-org/run-1/organisation-checks/dependabot.json",
        ),
        (
            "load_repository_checks",
            "audit-runs/test-org/run-1/repositories/",
            "repository_name",
            "repositories",
            "audit-runs/test-org/run-1/repositories/test-repo.json",
        ),
        (
            "load_team_checks",
            "audit-runs/test-org/run-1/teams/",
            "team_slug",
            "teams",
            "audit-runs/test-org/run-1/teams/team-slug.json",
        ),
    ],
)
class TestDataLoaderParametrized:
    """Parametrized tests for data loading methods."""

    def test_load_checks_from_s3(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should load checks from S3 with derived names."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": key_example}]}
        ]
        payload = {field_name: "test-value", "result": "pass"}
        mock_s3.get_object.return_value = {
            "Body": Mock(read=Mock(return_value=json.dumps(payload).encode()))
        }

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert "test-value" in result

    def test_load_checks_derives_name_from_key_when_missing(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should derive name from key when field_name not in payload."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": key_example}]}
        ]
        payload = {"result": "pass"}  # Missing field_name
        mock_s3.get_object.return_value = {
            "Body": Mock(read=Mock(return_value=json.dumps(payload).encode()))
        }

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        # Should derive name from key (last part before .json)
        expected_name = key_example.rsplit("/", 1)[-1].removesuffix(".json")
        assert expected_name in result

    def test_load_checks_handles_list_exception(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should handle exceptions during list_objects_v2."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.side_effect = Exception("S3 error")

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}

    def test_load_checks_skips_non_dict_payload(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should skip payloads that are not dicts."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": key_example}]}
        ]
        mock_s3.get_object.return_value = {
            "Body": Mock(read=Mock(return_value=json.dumps(["array"]).encode()))
        }

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}

    def test_load_checks_skips_invalid_key_type(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should skip entries where Key is not a string."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": 123}, {"Key": None}]}
        ]

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}

    def test_load_checks_skips_empty_derived_name(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should skip checks with empty derived names."""
        mock_s3 = Mock()
        # Key ends with .json after / so derives to empty string
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": prefix + ".json"}]}
        ]
        mock_s3.get_object.return_value = {
            "Body": Mock(
                read=Mock(return_value=json.dumps({"result": "pass"}).encode())
            )
        }

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}

    def test_load_checks_skips_non_json_files(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should skip non-JSON files."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": prefix + "file.txt"}]}
        ]

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}

    def test_load_checks_handles_get_object_exception(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should handle exceptions when getting objects."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": key_example}]}
        ]
        mock_s3.get_object.side_effect = Exception("S3 error")

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}

    def test_load_checks_handles_json_parse_exception(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should handle JSON parsing exceptions."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": key_example}]}
        ]
        mock_s3.get_object.return_value = {
            "Body": Mock(read=Mock(return_value=b"invalid json {"))
        }

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}

    def test_load_checks_handles_empty_response(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should handle S3 responses with no Contents key."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [{"Contents": []}]

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}

    def test_load_checks_handles_missing_contents_key(
        self, method_name, prefix, field_name, log_context, key_example
    ) -> None:
        """Should handle S3 responses without Contents key."""
        mock_s3 = Mock()
        mock_s3.get_paginator.return_value.paginate.return_value = [{}]

        loader = DataLoader(
            environment="prod", bucket_name="my-bucket", s3_client=mock_s3
        )
        method = getattr(loader, method_name)
        result = method("test-org", "run-1")

        assert result == {}


class TestNormalizers:
    """Test data normalization functions."""

    def test_is_pass_recognizes_pass_result(self) -> None:
        """is_pass should return True for 'pass' result."""
        assert is_pass({"result": "pass"}) is True
        assert is_pass({"result": "PASS"}) is True
        assert is_pass({"result": "fail"}) is False
        assert is_pass({}) is False
        assert is_pass({"no_result": True}) is False

    def test_normalise_organisation_checks_extracts_result_and_message(self) -> None:
        """Should extract result and message from organisation checks."""
        org_checks = {
            "dependabot": {
                "result": "pass",
                "message": "Dependabot is enabled",
                "timestamp": "2024-01-01T00:00:00Z",
                "extra_field": "ignored",
            }
        }

        result = normalise_organisation_checks(org_checks)

        assert result == {
            "dependabot": {
                "result": "pass",
                "message": "Dependabot is enabled",
                "details": {},
            }
        }

    def test_normalise_organisation_checks_with_missing_fields(self) -> None:
        """Should provide defaults for missing fields."""
        org_checks = {
            "check1": {},
            "check2": {"result": "pass"},
        }

        result = normalise_organisation_checks(org_checks)

        assert result["check1"]["result"] == "unknown"
        assert result["check1"]["message"] == ""
        assert result["check2"]["result"] == "pass"
        assert result["check2"]["message"] == ""

    def test_normalise_organisation_checks_skips_non_dict(self) -> None:
        """Should skip non-dict check results."""
        org_checks: dict[str, Any] = {
            "valid": {"result": "pass"},
            "invalid": "not a dict",
        }

        result = normalise_organisation_checks(org_checks)

        assert "valid" in result
        assert "invalid" not in result

    @pytest.mark.parametrize(
        "normalise_func,item_key",
        [
            (normalise_repository_checks, "repo1"),
            (normalise_team_checks, "team1"),
        ],
    )
    def test_normalise_items_with_compliance(self, normalise_func, item_key) -> None:
        """Should include is_compliant field."""
        items = {
            item_key: {
                "checks": {"check1": {"result": "pass"}},
            }
        }

        result = normalise_func(items)

        assert "is_compliant" in result[item_key]
        assert result[item_key]["is_compliant"] is True

    @pytest.mark.parametrize(
        "normalise_func,item_key",
        [
            (normalise_repository_checks, "repo1"),
            (normalise_team_checks, "team1"),
        ],
    )
    def test_normalise_items_non_compliant_on_fail(
        self, normalise_func, item_key
    ) -> None:
        """Should be non-compliant when any check fails."""
        items = {
            item_key: {
                "checks": {
                    "check1": {"result": "pass"},
                    "check2": {"result": "fail"},
                }
            }
        }

        result = normalise_func(items)

        assert result[item_key]["is_compliant"] is False

    @pytest.mark.parametrize(
        "normalise_func,item_key",
        [
            (normalise_repository_checks, "repo1"),
            (normalise_team_checks, "team1"),
        ],
    )
    def test_normalise_items_with_invalid_checks_dict(
        self, normalise_func, item_key
    ) -> None:
        """Should handle non-dict checks field."""
        items = {item_key: {"checks": "not a dict"}}

        result = normalise_func(items)

        assert item_key in result
        assert result[item_key]["checks"] == {}

    @pytest.mark.parametrize(
        "normalise_func,item_key",
        [
            (normalise_repository_checks, "repo1"),
            (normalise_team_checks, "team1"),
        ],
    )
    def test_normalise_items_skips_non_dict_items(
        self, normalise_func, item_key
    ) -> None:
        """Should skip non-dict items."""
        items = {
            "valid": {"checks": {"check1": {"result": "pass"}}},
            "invalid": "not a dict",
        }

        result = normalise_func(items)

        assert "valid" in result
        assert "invalid" not in result

    @pytest.mark.parametrize(
        "normalise_func,item_key",
        [
            (normalise_repository_checks, "repo1"),
            (normalise_team_checks, "team1"),
        ],
    )
    def test_normalise_items_with_missing_check_fields(
        self, normalise_func, item_key
    ) -> None:
        """Should provide defaults for missing check fields."""
        items = {
            item_key: {
                "checks": {
                    "check1": {},
                    "check2": {"result": "pass"},
                }
            }
        }

        result = normalise_func(items)

        assert result[item_key]["checks"]["check1"]["result"] == "unknown"
        assert result[item_key]["checks"]["check1"]["message"] == ""
        assert result[item_key]["checks"]["check2"]["result"] == "pass"

    @pytest.mark.parametrize(
        "normalise_func,item_key",
        [
            (normalise_repository_checks, "repo1"),
            (normalise_team_checks, "team1"),
        ],
    )
    def test_normalise_items_with_non_string_keys(
        self, normalise_func, item_key
    ) -> None:
        """Should handle non-string keys."""
        items = {
            "valid": {"checks": {"check1": {"result": "pass"}}},
            123: {"checks": {"check1": {"result": "pass"}}},
        }

        result = normalise_func(items)

        assert "valid" in result
        assert 123 in result


class TestOutputGenerator:
    """Test output generation and summary building."""

    def test_build_summary_counts_compliant_items(self) -> None:
        """Summary should count compliant repositories and teams."""
        repo_checks = {
            "repo1": {"is_compliant": True},
            "repo2": {"is_compliant": False},
        }
        team_checks = {
            "team1": {"is_compliant": True},
            "team2": {"is_compliant": True},
            "team3": {"is_compliant": False},
        }
        org_checks = {"check1": {"result": "pass"}}
        ratings = [{"name": "gold", "min_compliance": 100.0, "required_checks": []}]

        summary = build_summary(repo_checks, org_checks, team_checks, ratings)

        assert summary["compliant_repositories"] == 1
        assert summary["total_repositories"] == 2
        assert summary["compliant_teams"] == 2
        assert summary["total_teams"] == 3

    def test_build_summary_handles_empty_data(self) -> None:
        """Summary should handle empty data gracefully."""
        summary = build_summary({}, {}, {}, [])

        assert summary["compliant_repositories"] == 0
        assert summary["total_repositories"] == 0
        assert summary["compliant_teams"] == 0
        assert summary["total_teams"] == 0

    def test_build_summary_builds_check_summaries(self) -> None:
        """Summary should include check summaries."""
        repo_checks = {
            "repo1": {
                "is_compliant": True,
                "checks": {
                    "readme": {"result": "pass"},
                    "codeowners": {"result": "pass"},
                },
            },
            "repo2": {
                "is_compliant": False,
                "checks": {
                    "readme": {"result": "pass"},
                    "codeowners": {"result": "fail"},
                },
            },
        }
        org_checks = {"dependabot": {"result": "pass"}}
        team_checks = {
            "team1": {
                "is_compliant": True,
                "checks": {"maintainer": {"result": "pass"}},
            },
        }
        ratings: list[Any] = []

        summary = build_summary(repo_checks, org_checks, team_checks, ratings)

        # Check repository check summary
        assert summary["repository_checks"]["readme"]["total"] == 2
        assert summary["repository_checks"]["readme"]["compliant"] == 2
        assert summary["repository_checks"]["codeowners"]["total"] == 2
        assert summary["repository_checks"]["codeowners"]["compliant"] == 1

        # Check organisation check summary
        assert summary["organisation_checks"]["dependabot"]["compliant"] is True

        # Check team check summary
        assert summary["team_checks"]["maintainer"]["total"] == 1
        assert summary["team_checks"]["maintainer"]["compliant"] == 1

    def test_build_summary_calculates_ratings(self) -> None:
        """Summary should calculate repository ratings."""
        repo_checks = {
            "repo1": {"is_compliant": True, "checks": {}},
            "repo2": {"is_compliant": False, "checks": {}},
        }
        ratings = [
            {"name": "gold", "min_compliance": 100.0, "required_checks": []},
            {"name": "silver", "min_compliance": 50.0, "required_checks": []},
        ]

        summary = build_summary(repo_checks, {}, {}, ratings)

        assert "repository_ratings" in summary
        assert "gold" in summary["repository_ratings"]
        assert "silver" in summary["repository_ratings"]

    def test_build_summary_handles_non_dict_items(self) -> None:
        """Summary should skip non-dict items in collections."""
        repo_checks: dict[str, Any] = {
            "repo1": {"is_compliant": True},
            "invalid": "not a dict",
        }
        team_checks: dict[str, Any] = {
            "team1": {"is_compliant": True},
            "invalid": "not a dict",
        }

        summary = build_summary(repo_checks, {}, team_checks, [])

        assert summary["total_repositories"] == 2
        assert summary["compliant_repositories"] == 1
        assert summary["total_teams"] == 2
        assert summary["compliant_teams"] == 1

    def test_build_summary_skips_non_dict_in_check_summary(self) -> None:
        """Should skip non-dict items when building check summary."""
        repo_checks: dict[str, Any] = {
            "repo1": {"checks": {"readme": {"result": "pass"}}},
            "invalid": "not a dict",
        }
        team_checks: dict[str, Any] = {
            "team1": {"checks": {"maintainer": {"result": "pass"}}},
            "invalid": "not a dict",
        }

        summary = build_summary(repo_checks, {}, team_checks, [])

        assert summary["repository_checks"]["readme"]["total"] == 1
        assert summary["team_checks"]["maintainer"]["total"] == 1


class TestHandlerFunction:
    """Test main handler function."""

    def test_handler_raises_on_invalid_environment(self, monkeypatch) -> None:
        """Handler should raise ValueError for invalid ENVIRONMENT."""
        monkeypatch.setenv("ENVIRONMENT", "invalid")

        with pytest.raises(ValueError, match="ENVIRONMENT must be either"):
            handler({"owner": "test-org", "run_id": "run-1"}, None)

    def test_handler_raises_on_prod_without_bucket(self, monkeypatch) -> None:
        """Handler should raise ValueError in prod without output_bucket."""
        monkeypatch.setenv("ENVIRONMENT", "prod")

        with pytest.raises(
            ValueError, match=r"output_bucket \(or S3_BUCKET_NAME\) is required"
        ):
            handler({"owner": "test-org", "run_id": "run-1"}, None)

    @patch("functions.storage_functions.store_output.handler.boto3")
    @patch("functions.storage_functions.store_output.handler.load_scorecard_criteria")
    def test_handler_local_mode_returns_success(
        self, mock_load_criteria, mock_boto3, monkeypatch, tmp_path
    ) -> None:
        """Handler should process successfully in local mode."""
        monkeypatch.setenv("ENVIRONMENT", "local")
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "scorecard_criteria.json"
        config_file.write_text(
            json.dumps({"gold": {"min_compliance": 90, "required_checks": []}})
        )

        mock_load_criteria.return_value = [
            {"name": "gold", "min_compliance": 90.0, "required_checks": []}
        ]

        result = handler(
            {
                "owner": "test-org",
                "run_id": "run-1",
                "rate_limit_start": "2024-01-01T00:00:00Z",
                "rate_limit_end": "2024-01-01T01:00:00Z",
            },
            None,
        )

        assert result["status"] == "success"
        assert result["environment"] == "local"
        assert result["key"] is None

    @patch("functions.storage_functions.store_output.handler.boto3")
    @patch("functions.storage_functions.store_output.handler.load_scorecard_criteria")
    def test_handler_prod_mode_stores_to_s3(
        self, mock_load_criteria, mock_boto3, monkeypatch
    ) -> None:
        """Handler should store results to S3 in prod mode."""
        monkeypatch.setenv("ENVIRONMENT", "prod")

        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        mock_load_criteria.return_value = [
            {"name": "gold", "min_compliance": 90.0, "required_checks": []}
        ]

        with patch(
            "functions.storage_functions.store_output.handler.DataLoader"
        ) as MockLoader:
            mock_loader = MagicMock()
            MockLoader.return_value = mock_loader
            mock_loader.load_organisation_checks.return_value = {}
            mock_loader.load_repository_checks.return_value = {}
            mock_loader.load_team_checks.return_value = {}

            handler(
                {
                    "owner": "test-org",
                    "run_id": "run-1",
                    "output_bucket": "my-bucket",
                    "rate_limit_start": "2024-01-01T00:00:00Z",
                    "rate_limit_end": "2024-01-01T01:00:00Z",
                },
                None,
            )

            assert mock_s3_client.put_object.called
            call_args = mock_s3_client.put_object.call_args
            assert call_args[1]["Bucket"] == "my-bucket"
            assert "audit-results/test-org/run-1.json" in call_args[1]["Key"]

    def test_handler_default_environment_is_local(self, monkeypatch, tmp_path) -> None:
        """Handler should default to local environment if ENVIRONMENT not set."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "scorecard_criteria.json"
        config_file.write_text(
            json.dumps({"gold": {"min_compliance": 90, "required_checks": []}})
        )

        with patch(
            "functions.storage_functions.store_output.handler.load_scorecard_criteria"
        ) as mock_load:
            mock_load.return_value = [
                {"name": "gold", "min_compliance": 90.0, "required_checks": []}
            ]

            result = handler(
                {"owner": "test-org", "run_id": "run-1"},
                None,
            )

            assert result["environment"] == "local"

    @patch("functions.storage_functions.store_output.handler.boto3")
    @patch("functions.storage_functions.store_output.handler.load_scorecard_criteria")
    def test_handler_includes_all_required_output_fields(
        self, mock_load_criteria, mock_boto3, monkeypatch, tmp_path
    ) -> None:
        """Handler should include all required fields in output."""
        monkeypatch.setenv("ENVIRONMENT", "local")
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "scorecard_criteria.json"
        config_file.write_text(
            json.dumps({"gold": {"min_compliance": 90, "required_checks": []}})
        )

        mock_load_criteria.return_value = [
            {"name": "gold", "min_compliance": 90.0, "required_checks": []}
        ]

        handler(
            {
                "owner": "test-org",
                "run_id": "run-1",
                "rate_limit_start": "2024-01-01T00:00:00Z",
                "rate_limit_end": "2024-01-01T01:00:00Z",
            },
            None,
        )

        output_dir = tmp_path / "outputs" / "audit-results" / "test-org"
        output_file = output_dir / "run-1.json"
        assert output_file.exists()

        with open(output_file, "r") as f:
            output = json.load(f)

        assert output["owner"] == "test-org"
        assert output["run_id"] == "run-1"
        assert "repositories" in output
        assert "scorecard_criteria" in output
        assert "organisation_checks" in output
        assert "teams" in output
        assert "summary" in output
        assert "timestamp" in output
        assert output["rate_limit_start"] == "2024-01-01T00:00:00Z"
        assert output["rate_limit_end"] == "2024-01-01T01:00:00Z"

    @patch("functions.storage_functions.store_output.handler.boto3")
    @patch("functions.storage_functions.store_output.handler.load_scorecard_criteria")
    def test_handler_adds_ratings_to_repositories(
        self, mock_load_criteria, mock_boto3, monkeypatch, tmp_path
    ) -> None:
        """Handler should add ratings to repository checks."""
        monkeypatch.setenv("ENVIRONMENT", "local")
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "scorecard_criteria.json"
        config_file.write_text(
            json.dumps({"gold": {"min_compliance": 90, "required_checks": []}})
        )

        mock_load_criteria.return_value = [
            {"name": "gold", "min_compliance": 100.0, "required_checks": []},
            {"name": "silver", "min_compliance": 50.0, "required_checks": []},
        ]

        with patch(
            "functions.storage_functions.store_output.handler.DataLoader"
        ) as MockLoader:
            mock_loader = MagicMock()
            MockLoader.return_value = mock_loader
            mock_loader.load_organisation_checks.return_value = {}
            mock_loader.load_repository_checks.return_value = {
                "test-repo": {
                    "repository_name": "test-repo",
                    "checks": {"readme": {"result": "pass"}},
                }
            }
            mock_loader.load_team_checks.return_value = {}

            handler(
                {"owner": "test-org", "run_id": "run-1"},
                None,
            )

            output_dir = tmp_path / "outputs" / "audit-results" / "test-org"
            output_file = output_dir / "run-1.json"

            with open(output_file, "r") as f:
                output = json.load(f)

            assert "rating" in output["repositories"]["test-repo"]

    def test_handler_case_insensitive_environment(self, monkeypatch, tmp_path) -> None:
        """Handler should accept uppercase ENVIRONMENT values."""
        monkeypatch.setenv("ENVIRONMENT", "LOCAL")
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "scorecard_criteria.json"
        config_file.write_text(
            json.dumps({"gold": {"min_compliance": 90, "required_checks": []}})
        )

        with patch(
            "functions.storage_functions.store_output.handler.load_scorecard_criteria"
        ) as mock_load:
            mock_load.return_value = [
                {"name": "gold", "min_compliance": 90.0, "required_checks": []}
            ]

            result = handler(
                {"owner": "test-org", "run_id": "run-1"},
                None,
            )

            assert result["environment"] == "local"
