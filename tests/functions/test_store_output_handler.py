"""Unit tests for store_output Lambda handler."""

from __future__ import annotations

import importlib
import json

import pytest


@pytest.fixture()
def module():
    return importlib.import_module("functions.store_output.handler")


# ---------------------------------------------------------------------------
# _is_pass helper
# ---------------------------------------------------------------------------


def test_is_pass_returns_true_for_pass_status(module) -> None:
    assert module._is_pass({"status": "pass"}) is True


def test_is_pass_is_case_insensitive(module) -> None:
    assert module._is_pass({"status": "PASS"}) is True
    assert module._is_pass({"status": "Pass"}) is True


def test_is_pass_returns_false_for_fail_status(module) -> None:
    assert module._is_pass({"status": "fail"}) is False


def test_is_pass_returns_false_for_missing_status(module) -> None:
    assert module._is_pass({}) is False


def test_is_pass_returns_false_for_non_dict(module) -> None:
    assert module._is_pass("pass") is False
    assert module._is_pass(None) is False
    assert module._is_pass(["pass"]) is False


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_handler_raises_for_missing_owner(module) -> None:
    with pytest.raises(ValueError, match="owner"):
        module.handler({}, None)


def test_handler_raises_for_empty_owner(module) -> None:
    with pytest.raises(ValueError, match="owner"):
        module.handler({"owner": ""}, None)


def test_handler_raises_when_repositories_not_a_dict(module) -> None:
    with pytest.raises(ValueError, match="repositories"):
        module.handler({"owner": "test-org", "repositories": ["repo1"]}, None)


def test_handler_raises_when_teams_not_a_dict(module) -> None:
    with pytest.raises(ValueError, match="teams"):
        module.handler({"owner": "test-org", "teams": "bad"}, None)


def test_handler_raises_when_organisation_checks_not_a_dict(module) -> None:
    with pytest.raises(ValueError, match="organisation_checks"):
        module.handler({"owner": "test-org", "organisation_checks": 42}, None)


def test_handler_raises_for_invalid_environment(
    module, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(ValueError, match="ENVIRONMENT"):
        module.handler({"owner": "test-org"}, None)


# ---------------------------------------------------------------------------
# Local environment
# ---------------------------------------------------------------------------


def test_handler_local_writes_json_file(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.chdir(tmp_path)

    event = {
        "owner": "test-org",
        "repositories": {
            "repo-a": {"naming_convention": {"status": "pass"}},
            "repo-b": {"naming_convention": {"status": "fail"}},
        },
        "teams": {},
        "organisation_checks": {"dependabot_slo": {"status": "pass"}},
    }

    result = module.handler(event, None)

    assert result["status"] == "success"
    assert result["environment"] == "local"
    assert result["bucket"] is None
    assert result["owner"] == "test-org"

    output_file = tmp_path / result["local_output_path"]
    assert output_file.exists()

    written = json.loads(output_file.read_text())
    assert written["owner"] == "test-org"
    assert "timestamp" in written
    assert "summary" in written


def test_handler_local_summary_counts_compliant_repositories(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.chdir(tmp_path)

    event = {
        "owner": "test-org",
        "repositories": {
            "repo-a": {"check_x": {"status": "pass"}, "check_y": {"status": "pass"}},
            "repo-b": {"check_x": {"status": "pass"}, "check_y": {"status": "fail"}},
            "repo-c": {"check_x": {"status": "pass"}, "check_y": {"status": "pass"}},
        },
    }

    module.handler(event, None)

    # Re-read the written output to inspect summary
    output_dir = tmp_path / "outputs" / "test-org"
    files = list(output_dir.glob("*.json"))
    assert len(files) == 1
    written = json.loads(files[0].read_text())

    summary = written["summary"]
    assert summary["total_repositories"] == 3
    assert summary["compliant_repositories"] == 2


def test_handler_local_skips_non_dict_repository_checks(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.chdir(tmp_path)

    event = {
        "owner": "test-org",
        "repositories": {
            "repo-a": {"naming_convention": {"status": "pass"}},
            "repo-b": "not-a-dict",
        },
    }

    module.handler(event, None)

    output_dir = tmp_path / "outputs" / "test-org"
    files = list(output_dir.glob("*.json"))
    written = json.loads(files[0].read_text())

    check_summary = written["summary"]["repository_checks"]["naming_convention"]
    assert check_summary["total"] == 1
    assert check_summary["compliant"] == 1


def test_handler_local_summary_aggregates_repository_checks(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.chdir(tmp_path)

    event = {
        "owner": "test-org",
        "repositories": {
            "repo-a": {"naming_convention": {"status": "pass"}},
            "repo-b": {"naming_convention": {"status": "fail"}},
            "repo-c": {"naming_convention": {"status": "pass"}},
        },
    }

    module.handler(event, None)

    output_dir = tmp_path / "outputs" / "test-org"
    files = list(output_dir.glob("*.json"))
    written = json.loads(files[0].read_text())

    check_summary = written["summary"]["repository_checks"]["naming_convention"]
    assert check_summary["total"] == 3
    assert check_summary["compliant"] == 2


def test_handler_local_summary_includes_organisation_checks(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.chdir(tmp_path)

    event = {
        "owner": "test-org",
        "organisation_checks": {
            "dependabot_slo": {"status": "pass"},
            "secret_scanning_slo": {"status": "fail"},
        },
    }

    module.handler(event, None)

    output_dir = tmp_path / "outputs" / "test-org"
    files = list(output_dir.glob("*.json"))
    written = json.loads(files[0].read_text())

    org_checks = written["summary"]["organisation_checks"]
    assert org_checks["dependabot_slo"]["compliant"] is True
    assert org_checks["secret_scanning_slo"]["compliant"] is False


def test_handler_local_summary_counts_compliant_teams(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.chdir(tmp_path)

    event = {
        "owner": "test-org",
        "teams": {
            "team-a": {"maintainer_check": {"status": "pass"}},
            "team-b": {"maintainer_check": {"status": "fail"}},
        },
    }

    module.handler(event, None)

    output_dir = tmp_path / "outputs" / "test-org"
    files = list(output_dir.glob("*.json"))
    written = json.loads(files[0].read_text())

    summary = written["summary"]
    assert summary["total_teams"] == 2
    assert summary["compliant_teams"] == 1


def test_handler_local_defaults_to_local_environment(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.chdir(tmp_path)

    result = module.handler({"owner": "test-org"}, None)

    assert result["environment"] == "local"
    assert result["local_output_path"] is not None


# ---------------------------------------------------------------------------
# Prod environment
# ---------------------------------------------------------------------------


def test_handler_prod_calls_s3_put_object(
    module, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("S3_BUCKET_NAME", "my-audit-bucket")

    captured: dict[str, object] = {}

    class FakeS3Client:
        def put_object(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(module.boto3, "client", lambda service: FakeS3Client())

    event = {
        "owner": "test-org",
        "repositories": {"repo-a": {"check_x": {"status": "pass"}}},
    }

    result = module.handler(event, None)

    assert result["status"] == "success"
    assert result["environment"] == "prod"
    assert result["bucket"] == "my-audit-bucket"
    assert result["local_output_path"] is None

    assert captured["Bucket"] == "my-audit-bucket"
    assert captured["ContentType"] == "application/json"
    assert "audit-results/test-org/" in str(captured["Key"])
    written = json.loads(str(captured["Body"]))
    assert written["owner"] == "test-org"


def test_handler_prod_raises_when_s3_bucket_name_missing(
    module, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)

    with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
        module.handler({"owner": "test-org"}, None)
