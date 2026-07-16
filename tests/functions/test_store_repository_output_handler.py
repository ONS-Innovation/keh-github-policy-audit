"""Unit tests for store_repository_output Lambda handler."""

import importlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestStoreRepositoryOutputValidation:
    module = importlib.import_module("functions.store_repository_output.handler")

    def test_requires_owner(self):
        with pytest.raises(ValueError, match="owner"):
            self.module.handler({"run_id": "run-1", "repository_name": "repo-a"}, None)

    def test_requires_run_id(self):
        with pytest.raises(ValueError, match="run_id"):
            self.module.handler(
                {"owner": "test-org", "repository_name": "repo-a"}, None
            )

    def test_requires_repository_name(self):
        with pytest.raises(ValueError, match="repository_name"):
            self.module.handler({"owner": "test-org", "run_id": "run-1"}, None)

    def test_raises_when_checks_not_dict_or_list(self):
        with pytest.raises(ValueError, match="checks"):
            self.module.handler(
                {
                    "owner": "test-org",
                    "run_id": "run-1",
                    "repository_name": "repo-a",
                    "checks": "invalid",
                },
                None,
            )

    def test_raises_for_invalid_environment(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            with pytest.raises(ValueError, match="ENVIRONMENT"):
                self.module.handler(
                    {
                        "owner": "test-org",
                        "run_id": "run-1",
                        "repository_name": "repo-a",
                        "checks": {},
                    },
                    None,
                )

    def test_raises_in_prod_when_bucket_missing(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=True):
            with pytest.raises(ValueError, match="output_bucket"):
                self.module.handler(
                    {
                        "owner": "test-org",
                        "run_id": "run-1",
                        "repository_name": "repo-a",
                        "checks": {},
                    },
                    None,
                )


class TestStoreRepositoryOutputLocal:
    module = importlib.import_module("functions.store_repository_output.handler")

    def setup_method(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp_dir.name)
        self._original_cwd = os.getcwd()
        os.chdir(self.tmp_path)

    def teardown_method(self):
        os.chdir(self._original_cwd)
        self._tmp_dir.cleanup()

    def test_writes_local_repository_file(self):
        event = {
            "owner": "test-org",
            "run_id": "run-123",
            "repository_name": "repo-a",
            "checks": [
                {"check_name": "readme", "status": "pass"},
                {"check_name": "codeowners", "status": "fail"},
            ],
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            result = self.module.handler(event, None)

        assert result["status"] == "success"
        output_file = self.tmp_path / result["local_output_path"]
        assert output_file.exists()

        written = json.loads(output_file.read_text())
        assert written["repository_name"] == "repo-a"
        assert set(written["checks"].keys()) == {"readme", "codeowners"}

    def test_skips_non_dict_check_entries_in_list(self):
        event = {
            "owner": "test-org",
            "run_id": "run-123",
            "repository_name": "repo-a",
            "checks": [
                "not-a-dict",
                {"check_name": "readme", "status": "pass"},
            ],
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "local"}):
            result = self.module.handler(event, None)

        output_file = self.tmp_path / result["local_output_path"]
        written = json.loads(output_file.read_text())
        assert written["checks"] == {
            "readme": {"check_name": "readme", "status": "pass"}
        }


class TestStoreRepositoryOutputProd:
    module = importlib.import_module("functions.store_repository_output.handler")

    def test_puts_to_s3(self):
        captured: dict[str, object] = {}

        class FakeS3Client:
            def put_object(self, **kwargs):
                captured.update(kwargs)

        event = {
            "owner": "test-org",
            "run_id": "run-123",
            "repository_name": "repo-a",
            "checks": {"readme": {"status": "pass"}},
            "output_bucket": "audit-bucket",
        }

        with (
            patch.dict(os.environ, {"ENVIRONMENT": "prod"}),
            patch.object(self.module.boto3, "client", return_value=FakeS3Client()),
        ):
            result = self.module.handler(event, None)

        assert result["bucket"] == "audit-bucket"
        assert captured["Bucket"] == "audit-bucket"
        assert captured["Key"] == "audit-runs/test-org/run-123/repositories/repo-a.json"
        assert captured["ContentType"] == "application/json"
