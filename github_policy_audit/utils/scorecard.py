"""Repository scorecard criteria loading and evaluation helpers."""

import json
from pathlib import Path
from typing import Any


LOCAL_SCORECARD_CONFIG_PATH = "config/scorecard_criteria.json"
S3_SCORECARD_CONFIG_KEY = "config/scorecard_criteria.json"


def _is_pass(check_output: Any) -> bool:
    """Return True when a check result reports a passing result.

    Args:
        check_output: The output of a single check, expected to be a dict with a
            ``result`` key whose value is ``"pass"`` (case-insensitive).

    Returns:
        ``True`` if ``check_output`` is a dict whose ``result`` field equals
        ``"pass"`` (case-insensitive), ``False`` otherwise.
    """
    return (
        isinstance(check_output, dict)
        and str(check_output.get("result", "")).lower() == "pass"
    )


def _normalise_scorecard_criteria(raw_criteria: Any) -> list[dict[str, Any]]:
    """Validate and normalise scorecard criteria into descending threshold order.

    Args:
        raw_criteria: A dict mapping rating names to rating config dicts, each
            containing ``min_compliance`` (numeric, 0–100) and optionally
            ``required_checks`` (list of check-name strings).

            Example input:
            {
                "gold": {
                    "min_compliance": 90,
                    "required_checks": ["check_a", "check_b"]
                },
                "silver": {
                    "min_compliance": 75,
                    "required_checks": ["check_a"]
                },
            }

    Returns:
        A list of normalised rating dicts, sorted by ``min_compliance``
        descending. Each dict has the keys ``name``, ``min_compliance``
        (float), and ``required_checks`` (sorted list of strings).

        Example output:
        [
            {
                "name": "gold",
                "min_compliance": 90.0,
                "required_checks": ["check_a", "check_b"]
            },
            {
                "name": "silver",
                "min_compliance": 75.0,
                "required_checks": ["check_a"]
            },
        ]

    Raises:
        ValueError: If ``raw_criteria`` is not a non-empty dict, any rating
            name is not a non-empty string, any rating value is not a dict,
            ``min_compliance`` is non-numeric, or ``min_compliance`` is outside
            the range 0–100.
    """
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
    """Load scorecard criteria from S3 in prod, or local config in local mode.

    Args:
        environment: The deployment environment. When ``"prod"``, criteria are
            fetched from S3; otherwise the local file at
            ``config/scorecard_criteria.json`` is used.
        bucket_name: Name of the S3 bucket that holds the config. Required when
            ``environment`` is ``"prod"``.
        s3_client: A boto3 S3 client (or compatible). Required when
            ``environment`` is ``"prod"``.

    Returns:
        A normalised list of rating dicts as returned by
        :func:`_normalise_scorecard_criteria`.

    Raises:
        ValueError: If ``environment`` is ``"prod"`` and either ``bucket_name``
            or ``s3_client`` is not provided, or if the loaded JSON fails
            validation inside :func:`_normalise_scorecard_criteria`.
        FileNotFoundError: If the local config file does not exist when running
            outside of prod.
    """
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
    """Return pass percentage from repository check outputs.

    Args:
        repository_checks: A dict mapping check names to their output dicts.
            The special key ``"is_compliant"`` is excluded from the calculation.

    Returns:
        The percentage of checks that report a passing result, rounded to two
        decimal places. Returns ``0.0`` when there are no eligible checks.
    """
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
    """Return the highest repository rating satisfied by the check results.

    Args:
        repository_checks: A dict mapping check names to their output dicts, as
            produced by the individual check handlers.
        scorecard_ratings: A normalised list of rating dicts (typically from
            :func:`load_scorecard_criteria`), sorted by ``min_compliance``
            descending.

    Returns:
        The name of the first rating whose ``min_compliance`` threshold and
        ``required_checks`` are all satisfied. Returns ``"non-compliant"`` if no
        rating is satisfied.
    """
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

    return "non-compliant"


def serialise_scorecard_criteria(
    scorecard_ratings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return persisted scorecard criteria without a top-level ratings key.

    Args:
        scorecard_ratings: A normalised list of rating dicts (typically from
            :func:`load_scorecard_criteria`).

    Returns:
        A dict mapping each rating name to a sub-dict containing
        ``min_compliance`` and ``required_checks``, suitable for JSON
        serialisation and storage.
    """
    criteria_output: dict[str, Any] = {}
    for rating in scorecard_ratings:
        criteria_output[rating["name"]] = {
            "min_compliance": rating["min_compliance"],
            "required_checks": rating["required_checks"],
        }
    return criteria_output
