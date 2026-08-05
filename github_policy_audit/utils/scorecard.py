"""Repository scorecard criteria loading and evaluation helpers."""

import json
from pathlib import Path
from typing import Any


LOCAL_SCORECARD_CONFIG_PATH = "config/scorecard_criteria.json"
S3_SCORECARD_CONFIG_KEY = "config/scorecard_criteria.json"


def _is_pass(check_output: Any) -> bool:
    """Return True when a check result reports a passing result."""
    return (
        isinstance(check_output, dict)
        and str(check_output.get("result", "")).lower() == "pass"
    )


def _normalise_scorecard_criteria(raw_criteria: Any) -> list[dict[str, Any]]:
    """Validate and normalise scorecard criteria into descending threshold order."""
    if not isinstance(raw_criteria, dict) or not raw_criteria:
        raise ValueError("scorecard criteria must be a non-empty dictionary")

    normalised: list[dict[str, Any]] = []
    for name, rating in raw_criteria.items():
        if not isinstance(name, str) or not name:
            raise ValueError("scorecard rating name must be a non-empty string")
        if not isinstance(rating, dict):
            raise ValueError("each scorecard rating value must be a dictionary")

        min_compliance = rating.get("min_compliance")
        required_checks = rating.get("required_checks", [])

        if not isinstance(min_compliance, (int, float)):
            raise ValueError("scorecard min_compliance must be numeric")
        if min_compliance < 0 or min_compliance > 100:
            raise ValueError("scorecard min_compliance must be between 0 and 100")
        if not isinstance(required_checks, list):
            raise ValueError("scorecard required_checks must be a list")

        cleaned_required_checks = sorted(
            {
                check_name
                for check_name in required_checks
                if isinstance(check_name, str) and check_name
            }
        )
        normalised.append(
            {
                "name": name,
                "min_compliance": float(min_compliance),
                "required_checks": cleaned_required_checks,
            }
        )

    return sorted(normalised, key=lambda rating: rating["min_compliance"], reverse=True)


def load_scorecard_criteria(
    *,
    environment: str,
    bucket_name: str | None,
    s3_client: Any = None,
) -> list[dict[str, Any]]:
    """Load scorecard criteria from S3 in prod, or local config in local mode."""
    if environment == "prod":
        if not bucket_name:
            raise ValueError(
                "output_bucket (or S3_BUCKET_NAME) is required to load scorecard criteria in prod"
            )
        if s3_client is None:
            raise ValueError("s3_client is required to load scorecard criteria in prod")

        payload = s3_client.get_object(
            Bucket=bucket_name,
            Key=S3_SCORECARD_CONFIG_KEY,
        )["Body"].read()
        criteria = json.loads(payload)
        return _normalise_scorecard_criteria(criteria)

    local_config_path = LOCAL_SCORECARD_CONFIG_PATH
    if not Path(local_config_path).exists():
        raise FileNotFoundError(
            f"Local scorecard config file not found at {local_config_path}"
        )

    with open(local_config_path, "r", encoding="utf-8") as file:
        criteria = json.load(file)

    return _normalise_scorecard_criteria(criteria)


def _calculate_repository_compliance_percentage(
    repository_checks: dict[str, Any],
) -> float:
    """Return pass percentage from repository check outputs."""
    check_outputs = [
        check_output
        for check_name, check_output in repository_checks.items()
        if check_name != "is_compliant"
    ]
    if not check_outputs:
        return 0.0

    passed_checks = sum(1 for check_output in check_outputs if _is_pass(check_output))
    return round((passed_checks / len(check_outputs)) * 100, 2)


def calculate_repository_rating(
    repository_checks: dict[str, Any],
    scorecard_ratings: list[dict[str, Any]],
) -> str:
    """Return the highest repository rating satisfied by the check results."""
    compliance_percentage = _calculate_repository_compliance_percentage(
        repository_checks
    )

    for rating in scorecard_ratings:
        required_checks = rating["required_checks"]
        meets_required_checks = all(
            _is_pass(repository_checks.get(check_name))
            for check_name in required_checks
        )
        if compliance_percentage >= rating["min_compliance"] and meets_required_checks:
            return rating["name"]

    return "unrated"


def serialise_scorecard_criteria(
    scorecard_ratings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return persisted scorecard criteria without a top-level ratings key."""
    criteria_output: dict[str, Any] = {}
    for rating in scorecard_ratings:
        criteria_output[rating["name"]] = {
            "min_compliance": rating["min_compliance"],
            "required_checks": rating["required_checks"],
        }
    return criteria_output
