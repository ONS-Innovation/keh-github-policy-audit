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

    def test_returns_true_for_pass_result(self):
        """A dict with result 'pass' should be considered passing."""
        assert self.module._is_pass({"result": "pass"})

    def test_is_case_insensitive(self):
        """Result matching should be case-insensitive."""
        assert self.module._is_pass({"result": "PASS"})
        assert self.module._is_pass({"result": "Pass"})

    def test_returns_false_for_fail_result(self):
        """A dict with result 'fail' should not be considered passing."""
        assert not self.module._is_pass({"result": "fail"})

    def test_returns_false_for_missing_result(self):
        """A dict without a result key should not be considered passing."""
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
# Normalise helpers — bad-input continue branches
# ---------------------------------------------------------------------------


class TestNormaliseRepositoryChecks:
    module = importlib.import_module("functions.store_output.handler")

    def test_skips_non_dict_repository_result_entries(self):
        """Non-dict entries in repository_results should be silently skipped."""
        result = self.module._normalise_repository_checks(
            None,
            ["not-a-dict", {"repository_name": "repo-a", "checks": []}],
        )
        assert result == {"repo-a": {"is_compliant": True}}

    def test_skips_repository_result_with_missing_name(self):
        """Entries without a repository_name should be silently skipped."""
        result = self.module._normalise_repository_checks(
            None,
            [{"checks": [{"check_name": "readme", "result": "pass"}]}],
        )
        assert result == {}

    def test_skips_non_dict_check_result_entries(self):
        """Non-dict check entries within a repository result should be skipped."""
        result = self.module._normalise_repository_checks(
            None,
            [
                {
                    "repository_name": "repo-a",
                    "checks": [
                        "not-a-dict",
                        {"check_name": "readme", "result": "pass"},
                    ],
                }
            ],
        )
        assert result == {
            "repo-a": {
                "readme": {"check_name": "readme", "result": "pass"},
                "is_compliant": True,
            }
        }


class TestNormaliseTeamChecks:
    module = importlib.import_module("functions.store_output.handler")

    def test_skips_non_dict_team_result_entries(self):
        """Non-dict entries in team_results should be silently skipped."""
        result = self.module._normalise_team_checks(
            [{"slug": "team-a"}, {"slug": "team-b"}],
            ["not-a-dict", {"check_name": "team_maintainer", "result": "pass"}],
        )
        assert result == {
            "team-b": {
                "team_maintainer": {"check_name": "team_maintainer", "result": "pass"},
                "is_compliant": True,
            }
        }

    def test_skips_team_result_with_missing_check_name(self):
        """Team results without a check_name should be silently skipped."""
        result = self.module._normalise_team_checks(
            [{"slug": "team-a"}],
            [{"result": "pass"}],
        )
        assert result == {}


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
                "repo-a": {"naming_convention": {"result": "pass"}},
                "repo-b": {"naming_convention": {"result": "fail"}},
            },
            "teams": {},
            "organisation_checks": {"dependabot_slo": {"result": "pass"}},
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
                    "check_x": {"result": "pass"},
                    "check_y": {"result": "pass"},
                },
                "repo-b": {
                    "check_x": {"result": "pass"},
                    "check_y": {"result": "fail"},
                },
                "repo-c": {
                    "check_x": {"result": "pass"},
                    "check_y": {"result": "pass"},
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
                "repo-a": {"naming_convention": {"result": "pass"}},
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
                "repo-a": {"naming_convention": {"result": "pass"}},
                "repo-b": {"naming_convention": {"result": "fail"}},
                "repo-c": {"naming_convention": {"result": "pass"}},
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
                "dependabot_slo": {"result": "pass"},
                "secret_scanning_slo": {"result": "fail"},
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
                "team-a": {"maintainer_check": {"result": "pass"}},
                "team-b": {"maintainer_check": {"result": "fail"}},
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

    def test_summary_derives_compliance_from_check_results(self):
        """Summary counts should derive compliance from check results."""
        event = {
            "owner": "test-org",
            "repositories": {
                "repo-a": {
                    "naming_convention": {"result": "pass"},
                    "is_compliant": True,
                },
                "repo-b": {
                    "naming_convention": {"result": "fail"},
                    "is_compliant": False,
                },
            },
            "teams": {
                "team-a": {
                    "maintainer_check": {"result": "pass"},
                    "is_compliant": True,
                },
                "team-b": {
                    "maintainer_check": {"result": "fail"},
                    "is_compliant": False,
                },
            },
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            self.module.handler(event, None)

        output_dir = self.tmp_path / "outputs" / "test-org"
        files = list(output_dir.glob("*.json"))
        written = json.loads(files[0].read_text())

        summary = written["summary"]
        assert summary["compliant_repositories"] == 1
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
                {"check_name": "dependabot_slo", "result": "pass"},
                {"check_name": "secret_scanning_slo", "result": "fail"},
                [
                    {"check_name": "team_maintainer", "result": "pass"},
                    {"check_name": "team_maintainer", "result": "fail"},
                ],
            ],
            "repository_results": [
                {
                    "repository_name": "repo-a",
                    "checks": [
                        {"check_name": "codeowners", "result": "pass"},
                        {"check_name": "readme", "result": "fail"},
                    ],
                },
                {
                    "repository_name": "repo-b",
                    "checks": [{"check_name": "codeowners", "result": "pass"}],
                },
            ],
            "team_results": [
                {"check_name": "team_maintainer", "result": "pass"},
                {"check_name": "team_maintainer", "result": "fail"},
            ],
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            result = self.module.handler(event, None)

        output_file = self.tmp_path / result["local_output_path"]
        written = json.loads(output_file.read_text())

        assert written["repositories"] == {
            "repo-a": {
                "codeowners": {"check_name": "codeowners", "result": "pass"},
                "readme": {"check_name": "readme", "result": "fail"},
                "is_compliant": False,
            },
            "repo-b": {
                "codeowners": {"check_name": "codeowners", "result": "pass"},
                "is_compliant": True,
            },
        }
        assert written["teams"] == {
            "team-a": {
                "team_maintainer": {"check_name": "team_maintainer", "result": "pass"},
                "is_compliant": True,
            },
            "team-b": {
                "team_maintainer": {"check_name": "team_maintainer", "result": "fail"},
                "is_compliant": False,
            },
        }
        assert written["organisation_checks"] == {
            "dependabot_slo": {"check_name": "dependabot_slo", "result": "pass"},
            "secret_scanning_slo": {
                "check_name": "secret_scanning_slo",
                "result": "fail",
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

    def test_s3_loader_skips_non_dict_payload_and_handles_fallback_paths(self) -> None:
        """Loader should skip non-dict payloads, fallback repo name from key, and allow empty checks payloads."""

        class FakeBody:
            def __init__(self, payload):
                self.payload = payload

            def read(self):
                return json.dumps(self.payload)

        class FakePaginator:
            def paginate(self, **kwargs):
                del kwargs
                return [
                    {
                        "Contents": [
                            {
                                "Key": "audit-runs/test-org/run-123/repositories/repo-a.json"
                            },
                            {
                                "Key": "audit-runs/test-org/run-123/repositories/repo-b.json"
                            },
                            {
                                "Key": "audit-runs/test-org/run-123/repositories/repo-c.json"
                            },
                            {"Key": "audit-runs/test-org/run-123/repositories/.json"},
                        ]
                    }
                ]

        class FakeS3Client:
            def get_paginator(self, operation_name):
                assert operation_name == "list_objects_v2"
                return FakePaginator()

            def get_object(self, **kwargs):
                key = kwargs["Key"]
                if key.endswith("repo-a.json"):
                    return {
                        "Body": FakeBody(
                            {
                                "checks": {
                                    "readme": {
                                        "check_name": "readme",
                                        "result": "pass",
                                    }
                                }
                            }
                        )
                    }
                if key.endswith("repo-b.json"):
                    return {
                        "Body": FakeBody(
                            {
                                "repository_name": "repo-b",
                                "checks": "unexpected-type",
                            }
                        )
                    }
                if key.endswith("repo-c.json"):
                    return {"Body": FakeBody("not-a-dict")}
                # Empty filename fallback (/.json) should be ignored.
                return {"Body": FakeBody({})}

        result = self.module._load_repository_checks_from_s3(
            s3_client=FakeS3Client(),
            bucket_name="bucket",
            owner="test-org",
            run_id="run-123",
        )

        assert result == {
            "repo-a": {
                "readme": {"check_name": "readme", "result": "pass"},
                "is_compliant": True,
            },
            "repo-b": {"is_compliant": False},
        }

    def test_loads_repository_results_from_run_prefix(self) -> None:
        """When run_id is provided, repository results should be loaded from audit-runs S3 objects."""

        class FakeBody:
            def __init__(self, payload: dict):
                self.payload = payload

            def read(self):
                return json.dumps(self.payload)

        captured: dict[str, object] = {}

        class FakePaginator:
            def paginate(self, **kwargs):
                captured["prefix"] = kwargs.get("Prefix")
                return [
                    {
                        "Contents": [
                            {
                                "Key": "audit-runs/test-org/run-123/repositories/repo-a.json",
                            },
                        ],
                    }
                ]

        class FakeS3Client:
            def get_paginator(self, operation_name):
                assert operation_name == "list_objects_v2"
                return FakePaginator()

            def get_object(self, **kwargs):
                assert kwargs["Key"].endswith("repo-a.json")
                return {
                    "Body": FakeBody(
                        {
                            "repository_name": "repo-a",
                            "checks": {
                                "readme": {
                                    "check_name": "readme",
                                    "result": "pass",
                                }
                            },
                        }
                    )
                }

            def put_object(self, **kwargs):
                captured.update(kwargs)

        event = {
            "owner": "test-org",
            "run_id": "run-123",
            "output_bucket": "my-audit-bucket",
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
        assert captured["prefix"] == "audit-runs/test-org/run-123/repositories/"
        written = json.loads(str(captured["Body"]))
        assert written["summary"]["total_repositories"] == 1
        assert written["summary"]["compliant_repositories"] == 1

    def test_calls_s3_put_object(self) -> None:
        """In the prod environment the handler should upload the result to S3."""
        captured: dict[str, object] = {}

        class FakeS3Client:
            def put_object(self, **kwargs: object) -> None:
                captured.update(kwargs)

        event = {
            "owner": "test-org",
            "repositories": {"repo-a": {"check_x": {"result": "pass"}}},
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

    def test_raises_when_run_id_provided_in_prod_without_bucket(self):
        """Prod run_id aggregation requires an explicit output bucket."""
        event = {"owner": "test-org", "run_id": "run-123"}
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=True):
            with pytest.raises(ValueError, match="required in prod when using run_id"):
                self.module.handler(event, None)
