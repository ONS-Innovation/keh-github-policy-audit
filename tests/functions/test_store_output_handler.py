"""Unit tests for store_output Lambda handler."""

import importlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# _is_pass helper
# ---------------------------------------------------------------------------


class TestIsPass:
    module = importlib.import_module("functions.store_output.handler")

    def test_returns_true_for_pass_status(self):
        """A dict with status 'pass' should be considered passing."""
        assert self.module._is_pass({"status": "pass"})

    def test_is_case_insensitive(self):
        """Status matching should be case-insensitive."""
        assert self.module._is_pass({"status": "PASS"})
        assert self.module._is_pass({"status": "Pass"})

    def test_returns_false_for_fail_status(self):
        """A dict with status 'fail' should not be considered passing."""
        assert not self.module._is_pass({"status": "fail"})

    def test_returns_false_for_missing_status(self):
        """A dict without a status key should not be considered passing."""
        assert not self.module._is_pass({})

    def test_returns_false_for_non_dict(self):
        """Non-dict values should not be considered passing."""
        assert not self.module._is_pass("pass")
        assert not self.module._is_pass(None)
        assert not self.module._is_pass(["pass"])


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestHandlerValidation:
    module = importlib.import_module("functions.store_output.handler")

    def test_raises_for_missing_owner(self):
        """A missing owner key in the event should raise a ValueError."""
        with pytest.raises(ValueError, match="owner"):
            self.module.handler({}, None)

    def test_raises_for_empty_owner(self):
        """An empty owner value in the event should raise a ValueError."""
        with pytest.raises(ValueError, match="owner"):
            self.module.handler({"owner": ""}, None)

    def test_raises_when_repositories_not_a_dict(self):
        """A non-dict repositories value should raise a ValueError."""
        with pytest.raises(ValueError, match="repositories"):
            self.module.handler({"owner": "test-org", "repositories": ["repo1"]}, None)

    def test_raises_when_teams_not_a_dict(self):
        """A non-dict teams value should raise a ValueError."""
        with pytest.raises(ValueError, match="teams"):
            self.module.handler({"owner": "test-org", "teams": "bad"}, None)

    def test_raises_when_organisation_checks_not_a_dict(self):
        """A non-dict organisation_checks value should raise a ValueError."""
        with pytest.raises(ValueError, match="organisation_checks"):
            self.module.handler({"owner": "test-org", "organisation_checks": 42}, None)

    def test_raises_for_invalid_environment(self):
        """An unrecognised ENVIRONMENT value should raise a ValueError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            with pytest.raises(ValueError, match="ENVIRONMENT"):
                self.module.handler({"owner": "test-org"}, None)

    def test_raises_when_teams_list_without_team_results(self):
        """A teams list without team_results should raise a ValueError."""
        with pytest.raises(ValueError, match="team_results"):
            self.module.handler(
                {"owner": "test-org", "teams": [{"slug": "team-a"}]},
                None,
            )


# ---------------------------------------------------------------------------
# Local environment
# ---------------------------------------------------------------------------


class TestHandlerLocal:
    module = importlib.import_module("functions.store_output.handler")

    def setup_method(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp_dir.name)
        self._original_cwd = os.getcwd()
        os.chdir(self.tmp_path)

    def teardown_method(self):
        os.chdir(self._original_cwd)
        self._tmp_dir.cleanup()

    def test_writes_json_file(self):
        """The handler should write a JSON output file in the local environment."""
        event = {
            "owner": "test-org",
            "repositories": {
                "repo-a": {"naming_convention": {"status": "pass"}},
                "repo-b": {"naming_convention": {"status": "fail"}},
            },
            "teams": {},
            "organisation_checks": {"dependabot_slo": {"status": "pass"}},
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            result = self.module.handler(event, None)

        assert result["status"] == "success"
        assert result["environment"] == "local"
        assert result["bucket"] is None
        assert result["owner"] == "test-org"

        output_file = self.tmp_path / result["local_output_path"]
        assert output_file.exists()

        written = json.loads(output_file.read_text())
        assert written["owner"] == "test-org"
        assert "timestamp" in written
        assert "summary" in written

    def test_summary_counts_compliant_repositories(self):
        """The summary should count only repositories where all checks pass."""
        event = {
            "owner": "test-org",
            "repositories": {
                "repo-a": {
                    "check_x": {"status": "pass"},
                    "check_y": {"status": "pass"},
                },
                "repo-b": {
                    "check_x": {"status": "pass"},
                    "check_y": {"status": "fail"},
                },
                "repo-c": {
                    "check_x": {"status": "pass"},
                    "check_y": {"status": "pass"},
                },
            },
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            self.module.handler(event, None)

        output_dir = self.tmp_path / "outputs" / "test-org"
        files = list(output_dir.glob("*.json"))
        assert len(files) == 1
        written = json.loads(files[0].read_text())

        summary = written["summary"]
        assert summary["total_repositories"] == 3
        assert summary["compliant_repositories"] == 2

    def test_skips_non_dict_repository_checks(self):
        """Non-dict repository check values should be skipped when building the summary."""
        event = {
            "owner": "test-org",
            "repositories": {
                "repo-a": {"naming_convention": {"status": "pass"}},
                "repo-b": "not-a-dict",
            },
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            self.module.handler(event, None)

        output_dir = self.tmp_path / "outputs" / "test-org"
        files = list(output_dir.glob("*.json"))
        written = json.loads(files[0].read_text())

        check_summary = written["summary"]["repository_checks"]["naming_convention"]
        assert check_summary["total"] == 1
        assert check_summary["compliant"] == 1

    def test_summary_aggregates_repository_checks(self):
        """The summary should aggregate pass/fail counts per check across all repositories."""
        event = {
            "owner": "test-org",
            "repositories": {
                "repo-a": {"naming_convention": {"status": "pass"}},
                "repo-b": {"naming_convention": {"status": "fail"}},
                "repo-c": {"naming_convention": {"status": "pass"}},
            },
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            self.module.handler(event, None)

        output_dir = self.tmp_path / "outputs" / "test-org"
        files = list(output_dir.glob("*.json"))
        written = json.loads(files[0].read_text())

        check_summary = written["summary"]["repository_checks"]["naming_convention"]
        assert check_summary["total"] == 3
        assert check_summary["compliant"] == 2

    def test_summary_includes_organisation_checks(self):
        """The summary should include organisation-level check compliance."""
        event = {
            "owner": "test-org",
            "organisation_checks": {
                "dependabot_slo": {"status": "pass"},
                "secret_scanning_slo": {"status": "fail"},
            },
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            self.module.handler(event, None)

        output_dir = self.tmp_path / "outputs" / "test-org"
        files = list(output_dir.glob("*.json"))
        written = json.loads(files[0].read_text())

        org_checks = written["summary"]["organisation_checks"]
        assert org_checks["dependabot_slo"]["compliant"]
        assert not org_checks["secret_scanning_slo"]["compliant"]

    def test_summary_counts_compliant_teams(self):
        """The summary should count only teams where all checks pass."""
        event = {
            "owner": "test-org",
            "teams": {
                "team-a": {"maintainer_check": {"status": "pass"}},
                "team-b": {"maintainer_check": {"status": "fail"}},
            },
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            self.module.handler(event, None)

        output_dir = self.tmp_path / "outputs" / "test-org"
        files = list(output_dir.glob("*.json"))
        written = json.loads(files[0].read_text())

        summary = written["summary"]
        assert summary["total_teams"] == 2
        assert summary["compliant_teams"] == 1

    def test_defaults_to_local_environment(self):
        """The handler should default to the local environment when ENVIRONMENT is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENVIRONMENT", None)
            result = self.module.handler({"owner": "test-org"}, None)

        assert result["environment"] == "local"
        assert result["local_output_path"] is not None

    def test_normalises_step_function_raw_results(self):
        """The handler should reshape Step Function array outputs into keyed dictionaries."""
        event = {
            "owner": "test-org",
            "teams": [{"slug": "team-a"}, {"slug": "team-b"}],
            "organisation_results": [
                {"check_name": "dependabot_slo", "status": "pass"},
                {"check_name": "secret_scanning_slo", "status": "fail"},
                [
                    {"check_name": "team_maintainer", "status": "pass"},
                    {"check_name": "team_maintainer", "status": "fail"},
                ],
            ],
            "repository_results": [
                {
                    "repository_name": "repo-a",
                    "checks": [
                        {"check_name": "codeowners", "status": "pass"},
                        {"check_name": "readme", "status": "fail"},
                    ],
                },
                {
                    "repository_name": "repo-b",
                    "checks": [{"check_name": "codeowners", "status": "pass"}],
                },
            ],
            "team_results": [
                {"check_name": "team_maintainer", "status": "pass"},
                {"check_name": "team_maintainer", "status": "fail"},
            ],
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            result = self.module.handler(event, None)

        output_file = self.tmp_path / result["local_output_path"]
        written = json.loads(output_file.read_text())

        assert written["repositories"] == {
            "repo-a": {
                "codeowners": {"check_name": "codeowners", "status": "pass"},
                "readme": {"check_name": "readme", "status": "fail"},
            },
            "repo-b": {"codeowners": {"check_name": "codeowners", "status": "pass"}},
        }
        assert written["teams"] == {
            "team-a": {
                "team_maintainer": {"check_name": "team_maintainer", "status": "pass"}
            },
            "team-b": {
                "team_maintainer": {"check_name": "team_maintainer", "status": "fail"}
            },
        }
        assert written["organisation_checks"] == {
            "dependabot_slo": {"check_name": "dependabot_slo", "status": "pass"},
            "secret_scanning_slo": {
                "check_name": "secret_scanning_slo",
                "status": "fail",
            },
        }
        assert written["summary"]["total_repositories"] == 2
        assert written["summary"]["compliant_repositories"] == 1
        assert written["summary"]["total_teams"] == 2
        assert written["summary"]["compliant_teams"] == 1


# ---------------------------------------------------------------------------
# Prod environment
# ---------------------------------------------------------------------------


class TestHandlerProd:
    module = importlib.import_module("functions.store_output.handler")

    def test_calls_s3_put_object(self) -> None:
        """In the prod environment the handler should upload the result to S3."""
        captured: dict[str, object] = {}

        class FakeS3Client:
            def put_object(self, **kwargs: object) -> None:
                captured.update(kwargs)

        event = {
            "owner": "test-org",
            "repositories": {"repo-a": {"check_x": {"status": "pass"}}},
        }

        with (
            patch.dict(
                os.environ,
                {"ENVIRONMENT": "prod", "S3_BUCKET_NAME": "my-audit-bucket"},
            ),
            patch.object(self.module.boto3, "client", return_value=FakeS3Client()),
        ):
            result = self.module.handler(event, None)

        assert result["status"] == "success"
        assert result["environment"] == "prod"
        assert result["bucket"] == "my-audit-bucket"
        assert result["local_output_path"] is None

        assert captured["Bucket"] == "my-audit-bucket"
        assert captured["ContentType"] == "application/json"
        assert "audit-results/test-org/" in str(captured["Key"])
        written = json.loads(str(captured["Body"]))
        assert written["owner"] == "test-org"

    def test_raises_when_s3_bucket_name_missing(self):
        """A missing S3_BUCKET_NAME in prod should raise a ValueError."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=False):
            os.environ.pop("S3_BUCKET_NAME", None)
            with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
                self.module.handler({"owner": "test-org"}, None)
