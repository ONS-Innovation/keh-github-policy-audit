"""Lambda handler to aggregate and store audit output from S3.

This handler:
1. Loads individual check results from S3 (produced during the audit run)
2. Aggregates and normalises the data
3. Calculates compliance scores and ratings
4. Stores the final output to S3

For local testing (ENVIRONMENT=local), loads data from local files under
outputs/audit-runs/{owner}/{run_id}/ instead of S3, and writes output to
outputs/audit-results/{owner}/ instead of S3.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3

from utils.scorecard import calculate_repository_rating
from utils.scorecard import load_scorecard_criteria
from utils.scorecard import serialise_scorecard_criteria
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DataLoader:
    """Load audit data from S3 or local files depending on environment."""

    def __init__(self, environment: str, bucket_name: str | None, s3_client=None):
        self.environment = environment
        self.bucket_name = bucket_name
        self.s3_client = s3_client

    def _load_from_local(
        self, folder: str, field_name: str, log_context: str, owner: str, run_id: str
    ) -> dict[str, dict]:
        """Load audit data from local files in outputs directory."""
        result: dict[str, dict] = {}
        local_dir = Path("outputs") / "audit-runs" / owner / run_id / folder

        if not local_dir.exists():
            log_info(
                logger,
                f"local_directory_not_found_{log_context}",
                path=str(local_dir),
            )
            return result

        try:
            for json_file in local_dir.glob("*.json"):
                try:
                    with open(json_file, encoding="utf-8") as f:
                        payload = json.load(f)

                    if not isinstance(payload, dict):
                        continue

                    # Extract name from payload, fallback to filename
                    name = payload.get(field_name)
                    if not isinstance(name, str) or not name:
                        name = json_file.stem

                    if name:
                        result[name] = payload
                except Exception as e:
                    log_info(
                        logger,
                        f"failed_to_load_{log_context}",
                        file=json_file.name,
                        error=str(e),
                    )
                    continue
        except Exception as e:
            log_info(logger, f"failed_to_read_{log_context}", error=str(e))

        return result

    def _load_from_s3(
        self, prefix: str, field_name: str, log_context: str
    ) -> dict[str, dict]:
        """Generic loader for S3 objects with field-based naming."""
        result: dict[str, dict] = {}

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            for response in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in response.get("Contents", []):
                    key = obj.get("Key")
                    if not isinstance(key, str) or not key.endswith(".json"):
                        continue

                    try:
                        body = self.s3_client.get_object(
                            Bucket=self.bucket_name, Key=key
                        )["Body"].read()
                        payload = json.loads(body)

                        if not isinstance(payload, dict):
                            continue

                        # Extract name from payload, fallback to key
                        name = payload.get(field_name)
                        if not isinstance(name, str) or not name:
                            name = key.rsplit("/", 1)[-1].removesuffix(".json")

                        if name:
                            result[name] = payload
                    except Exception as e:
                        log_info(
                            logger,
                            f"failed_to_load_{log_context}",
                            key=key,
                            error=str(e),
                        )
                        continue
        except Exception as e:
            log_info(logger, f"failed_to_list_{log_context}", error=str(e))

        return result

    def load_organisation_checks(self, owner: str, run_id: str) -> dict[str, dict]:
        """Load organisation check results from local files or S3."""
        if self.environment == "local":
            return self._load_from_local(
                "organisation-checks",
                "check_name",
                "organisation_checks",
                owner,
                run_id,
            )

        prefix = f"audit-runs/{owner}/{run_id}/organisation-checks/"
        return self._load_from_s3(prefix, "check_name", "organisation_checks")

    def load_repository_checks(self, owner: str, run_id: str) -> dict[str, dict]:
        """Load per-repository results from local files or S3."""
        if self.environment == "local":
            return self._load_from_local(
                "repositories", "repository_name", "repositories", owner, run_id
            )

        prefix = f"audit-runs/{owner}/{run_id}/repositories/"
        return self._load_from_s3(prefix, "repository_name", "repositories")

    def load_team_checks(self, owner: str, run_id: str) -> dict[str, dict]:
        """Load per-team results from local files or S3."""
        if self.environment == "local":
            return self._load_from_local("teams", "team_slug", "teams", owner, run_id)

        prefix = f"audit-runs/{owner}/{run_id}/teams/"
        return self._load_from_s3(prefix, "team_slug", "teams")


def is_pass(check_result: Any) -> bool:
    """Return True if check result is a pass."""
    return (
        isinstance(check_result, dict)
        and str(check_result.get("result", "")).lower() == "pass"
    )


def _normalise_checks_with_compliance(
    items: dict[str, dict],
) -> dict[str, dict]:
    """Normalise items with compliance calculation."""
    normalised: dict[str, dict] = {}

    for item_name, item_data in items.items():
        if not isinstance(item_data, dict):
            continue

        checks = item_data.get("checks", {})
        if not isinstance(checks, dict):
            checks = {}

        normalised_checks = {}
        for check_name, check_result in checks.items():
            if isinstance(check_result, dict):
                normalised_checks[check_name] = {
                    "result": check_result.get("result", "unknown"),
                    "message": check_result.get("message", ""),
                }

        # Calculate compliance from checks (case insensitive)
        is_compliant = all(is_pass(check) for check in normalised_checks.values())

        normalised[item_name] = {
            "checks": normalised_checks,
            "is_compliant": is_compliant,
        }

    return normalised


def normalise_organisation_checks(checks: dict[str, dict]) -> dict[str, dict]:
    """Normalise organisation checks to consistent format."""
    normalised: dict[str, dict] = {}
    for check_name, check_data in checks.items():
        if isinstance(check_data, dict):
            normalised[check_name] = {
                "result": check_data.get("result", "unknown"),
                "message": check_data.get("message", ""),
                "details": check_data.get("details", {}),
            }
    return normalised


def normalise_repository_checks(repos: dict[str, dict]) -> dict[str, dict]:
    """Normalise repository checks to consistent format."""
    return _normalise_checks_with_compliance(repos)


def normalise_team_checks(teams: dict[str, dict]) -> dict[str, dict]:
    """Normalise team checks to consistent format."""
    return _normalise_checks_with_compliance(teams)


def _build_check_summary(items: dict[str, dict]) -> dict[str, dict]:
    """Build check summary for items (repos or teams)."""
    summary: dict[str, dict] = {}
    for item in items.values():
        if not isinstance(item, dict):
            continue
        for check_name, check_result in item.get("checks", {}).items():
            if check_name not in summary:
                summary[check_name] = {"total": 0, "compliant": 0}
            summary[check_name]["total"] += 1
            if is_pass(check_result):
                summary[check_name]["compliant"] += 1
    return summary


def build_summary(
    repositories: dict[str, dict],
    organisation_checks: dict[str, dict],
    teams: dict[str, dict],
    scorecard_ratings: list[dict],
) -> dict[str, Any]:
    """Build summary of audit results."""
    # Calculate repository compliance
    compliant_repos = sum(
        1
        for repo in repositories.values()
        if isinstance(repo, dict) and repo.get("is_compliant") is True
    )

    # Calculate team compliance
    compliant_teams = sum(
        1
        for team in teams.values()
        if isinstance(team, dict) and team.get("is_compliant") is True
    )

    # Build repository ratings from scorecard
    scorecard_status_counts = {rating["name"]: 0 for rating in scorecard_ratings}

    # Add non-compliant rating
    # This ensures that there is always a count for non-compliant repositories, even if none are found.
    scorecard_status_counts["non-compliant"] = 0

    for repo_checks in repositories.values():
        if isinstance(repo_checks, dict):
            checks = repo_checks.get("checks", {})
            if isinstance(checks, dict):
                rating = calculate_repository_rating(checks, scorecard_ratings)
                scorecard_status_counts[rating] = (
                    scorecard_status_counts.get(rating, 0) + 1
                )

    # Build check summaries using shared helper
    repository_check_summary = _build_check_summary(repositories)
    organisation_check_summary = {}
    for check_name, check_result in organisation_checks.items():
        organisation_check_summary[check_name] = {"compliant": is_pass(check_result)}
    team_check_summary = _build_check_summary(teams)

    return {
        "total_repositories": len(repositories),
        "compliant_repositories": compliant_repos,
        "total_teams": len(teams),
        "compliant_teams": compliant_teams,
        "repository_checks": repository_check_summary,
        "organisation_checks": organisation_check_summary,
        "team_checks": team_check_summary,
        "repository_ratings": scorecard_status_counts,
    }


def handler(event, context):
    """Aggregate audit results and store final output."""
    log_info(logger, "lambda_invoked", event_keys=sorted(event.keys()))

    # Extract required inputs
    owner = event["owner"]
    run_id = event["run_id"]
    output_bucket = event.get("output_bucket") or os.environ.get("S3_BUCKET_NAME")
    rate_limit_start = event.get("rate_limit_start")
    rate_limit_end = event.get("rate_limit_end")

    # Environment setup
    environment = (os.environ.get("ENVIRONMENT") or "local").lower()
    if environment not in {"local", "prod"}:
        raise ValueError("ENVIRONMENT must be either 'local' or 'prod'")

    if environment == "prod" and not output_bucket:
        raise ValueError("output_bucket (or S3_BUCKET_NAME) is required in production")

    s3_client = boto3.client("s3") if environment == "prod" else None

    # Load data
    loader = DataLoader(environment, output_bucket, s3_client)

    log_info(logger, "loading_data", environment=environment)
    org_checks_raw = loader.load_organisation_checks(owner, run_id)
    repo_checks_raw = loader.load_repository_checks(owner, run_id)
    team_checks_raw = loader.load_team_checks(owner, run_id)

    # Normalise data
    org_checks = normalise_organisation_checks(org_checks_raw)
    repo_checks = normalise_repository_checks(repo_checks_raw)
    team_checks = normalise_team_checks(team_checks_raw)

    # Add ratings to repositories
    scorecard_ratings = load_scorecard_criteria(
        environment=environment,
        bucket_name=output_bucket,
        s3_client=s3_client,
    )

    for repo_name, repo_data in repo_checks.items():
        if isinstance(repo_data, dict):
            checks = repo_data.get("checks", {})
            rating = calculate_repository_rating(checks, scorecard_ratings)
            repo_checks[repo_name]["rating"] = rating

    # Generate summary
    summary = build_summary(repo_checks, org_checks, team_checks, scorecard_ratings)

    # Build output
    now = datetime.now(timezone.utc)
    output = {
        "owner": owner,
        "run_id": run_id,
        "repositories": repo_checks,
        "scorecard_criteria": serialise_scorecard_criteria(scorecard_ratings),
        "organisation_checks": org_checks,
        "teams": team_checks,
        "summary": summary,
        "rate_limit_start": rate_limit_start,
        "rate_limit_end": rate_limit_end,
        "timestamp": now.isoformat(),
    }

    # Store output
    if environment == "prod":
        result_key = f"audit-results/{owner}/{run_id}.json"
        log_info(logger, "storing_results", bucket=output_bucket, key=result_key)

        s3_client.put_object(
            Bucket=output_bucket,
            Key=result_key,
            Body=json.dumps(output, indent=2),
            ContentType="application/json",
        )
    else:
        output_dir = os.path.join("outputs", "audit-results", owner)
        os.makedirs(output_dir, exist_ok=True)
        result_file = os.path.join(output_dir, f"{run_id}.json")

        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        log_info(logger, "stored_results_locally", path=result_file)

    log_info(
        logger,
        "lambda_completed",
        owner=owner,
        repositories_count=len(repo_checks),
        organisation_checks_count=len(org_checks),
        teams_count=len(team_checks),
    )

    return {
        "status": "success",
        "environment": environment,
        "bucket": output_bucket,
        "key": f"audit-results/{owner}/{run_id}.json"
        if environment == "prod"
        else None,
    }
