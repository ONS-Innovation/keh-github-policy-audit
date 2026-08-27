"""Unit tests for scorecard utility functions."""

import importlib
import json
from unittest.mock import MagicMock

import pytest


module = importlib.import_module("utils.scorecard")


# ---------------------------------------------------------------------------
# _normalise_scorecard_criteria
# ---------------------------------------------------------------------------


class TestNormaliseScorecardCriteria:
    def test_raises_for_empty_dict(self) -> None:
        """An empty dict should raise a ValueError."""
        with pytest.raises(
            ValueError, match="scorecard criteria must be a non-empty dictionary"
        ):
            module._normalise_scorecard_criteria({})

    def test_raises_for_non_dict_input(self) -> None:
        """A non-dict input should raise a ValueError."""
        with pytest.raises(
            ValueError, match="scorecard criteria must be a non-empty dictionary"
        ):
            module._normalise_scorecard_criteria(["not-a-dict"])

    def test_raises_for_non_string_rating_name(self) -> None:
        """An integer rating name should raise a ValueError."""
        with pytest.raises(
            ValueError, match="scorecard rating name must be a non-empty string"
        ):
            module._normalise_scorecard_criteria(
                {123: {"min_compliance": 50, "required_checks": []}}
            )

    def test_raises_for_empty_string_rating_name(self) -> None:
        """An empty string rating name should raise a ValueError."""
        with pytest.raises(
            ValueError, match="scorecard rating name must be a non-empty string"
        ):
            module._normalise_scorecard_criteria(
                {"": {"min_compliance": 50, "required_checks": []}}
            )

    def test_raises_when_rating_value_is_not_dict(self) -> None:
        """A non-dict rating value should raise a ValueError."""
        with pytest.raises(
            ValueError, match="each scorecard rating value must be a dictionary"
        ):
            module._normalise_scorecard_criteria({"gold": "not-a-dict"})

    def test_raises_when_min_compliance_not_numeric(self) -> None:
        """A non-numeric min_compliance should raise a ValueError."""
        with pytest.raises(
            ValueError, match="scorecard min_compliance must be numeric"
        ):
            module._normalise_scorecard_criteria(
                {"gold": {"min_compliance": "high", "required_checks": []}}
            )

    def test_raises_when_min_compliance_below_zero(self) -> None:
        """A min_compliance below 0 should raise a ValueError."""
        with pytest.raises(
            ValueError, match="scorecard min_compliance must be between 0 and 100"
        ):
            module._normalise_scorecard_criteria(
                {"gold": {"min_compliance": -1, "required_checks": []}}
            )

    def test_raises_when_min_compliance_above_100(self) -> None:
        """A min_compliance above 100 should raise a ValueError."""
        with pytest.raises(
            ValueError, match="scorecard min_compliance must be between 0 and 100"
        ):
            module._normalise_scorecard_criteria(
                {"gold": {"min_compliance": 101, "required_checks": []}}
            )

    def test_raises_when_required_checks_not_a_list(self) -> None:
        """A non-list required_checks should raise a ValueError."""
        with pytest.raises(
            ValueError, match="scorecard required_checks must be a list"
        ):
            module._normalise_scorecard_criteria(
                {"gold": {"min_compliance": 90, "required_checks": "readme"}}
            )

    def test_normalises_single_rating_successfully(self) -> None:
        """Should successfully normalise a single rating with valid criteria."""
        raw_criteria = {"gold": {"min_compliance": 90, "required_checks": ["readme"]}}

        result = module._normalise_scorecard_criteria(raw_criteria)

        assert len(result) == 1
        assert result[0]["name"] == "gold"
        assert result[0]["min_compliance"] == 90.0
        assert result[0]["required_checks"] == ["readme"]

    def test_normalises_multiple_ratings_and_sorts_by_compliance(self) -> None:
        """Should normalise multiple ratings and sort by min_compliance descending."""
        raw_criteria = {
            "silver": {"min_compliance": 50, "required_checks": ["readme"]},
            "gold": {"min_compliance": 90, "required_checks": ["readme", "codeowners"]},
            "bronze": {"min_compliance": 25, "required_checks": []},
        }

        result = module._normalise_scorecard_criteria(raw_criteria)

        assert len(result) == 3
        assert result[0]["name"] == "gold"
        assert result[0]["min_compliance"] == 90.0
        assert result[1]["name"] == "silver"
        assert result[1]["min_compliance"] == 50.0
        assert result[2]["name"] == "bronze"
        assert result[2]["min_compliance"] == 25.0

    def test_deduplicates_and_filters_required_checks(self) -> None:
        """Should deduplicate and filter out empty/non-string checks."""
        raw_criteria = {
            "gold": {
                "min_compliance": 90,
                "required_checks": ["readme", "readme", "", None, 123, "codeowners"],
            }
        }

        result = module._normalise_scorecard_criteria(raw_criteria)

        assert len(result) == 1
        assert result[0]["required_checks"] == ["codeowners", "readme"]  # sorted

    def test_handles_missing_required_checks_key(self) -> None:
        """Should use empty list as default when required_checks is omitted."""
        raw_criteria = {"gold": {"min_compliance": 90}}

        result = module._normalise_scorecard_criteria(raw_criteria)

        assert len(result) == 1
        assert result[0]["required_checks"] == []


# ---------------------------------------------------------------------------
# load_scorecard_criteria
# ---------------------------------------------------------------------------


class TestLoadScorecardCriteria:
    def test_raises_in_prod_without_bucket_name(self) -> None:
        """Prod mode without a bucket_name should raise a ValueError."""
        with pytest.raises(ValueError, match="output_bucket"):
            module.load_scorecard_criteria(
                environment="prod",
                bucket_name=None,
                s3_client=object(),
            )

    def test_raises_in_prod_without_s3_client(self) -> None:
        """Prod mode without an s3_client should raise a ValueError."""
        with pytest.raises(ValueError, match="s3_client is required"):
            module.load_scorecard_criteria(
                environment="prod",
                bucket_name="my-audit-bucket",
                s3_client=None,
            )

    def test_raises_in_local_when_config_file_missing(
        self, tmp_path, monkeypatch
    ) -> None:
        """Local mode should raise FileNotFoundError when the config file does not exist."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(
            FileNotFoundError, match="Local scorecard config file not found"
        ):
            module.load_scorecard_criteria(
                environment="local",
                bucket_name=None,
            )

    def test_loads_from_prod_s3_successfully(self) -> None:
        """Prod mode should successfully load and normalise criteria from S3."""
        mock_s3_client = MagicMock()
        criteria_data = {
            "gold": {"min_compliance": 90, "required_checks": ["readme"]},
            "silver": {"min_compliance": 50, "required_checks": []},
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=json.dumps(criteria_data).encode())
            )
        }

        result = module.load_scorecard_criteria(
            environment="prod",
            bucket_name="my-audit-bucket",
            s3_client=mock_s3_client,
        )

        assert len(result) == 2
        assert result[0]["name"] == "gold"
        assert result[0]["min_compliance"] == 90.0
        assert result[1]["name"] == "silver"
        assert result[1]["min_compliance"] == 50.0
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="my-audit-bucket",
            Key="config/scorecard_criteria.json",
        )

    def test_loads_from_local_config_successfully(self, tmp_path, monkeypatch) -> None:
        """Local mode should successfully load and normalise criteria from local file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "scorecard_criteria.json"

        criteria_data = {
            "gold": {"min_compliance": 90, "required_checks": ["readme"]},
            "silver": {"min_compliance": 50, "required_checks": []},
        }
        config_file.write_text(json.dumps(criteria_data))

        monkeypatch.chdir(tmp_path)

        result = module.load_scorecard_criteria(
            environment="local",
            bucket_name=None,
        )

        assert len(result) == 2
        assert result[0]["name"] == "gold"
        assert result[0]["min_compliance"] == 90.0
        assert result[1]["name"] == "silver"
        assert result[1]["min_compliance"] == 50.0


# ---------------------------------------------------------------------------
# calculate_repository_rating
# ---------------------------------------------------------------------------


class TestCalculateRepositoryRating:
    def test_all_passes_meets_highest_threshold(self) -> None:
        """All passing checks should match the highest compliance threshold."""
        checks = {"readme": {"result": "pass"}, "codeowners": {"result": "pass"}}
        ratings = [
            {"name": "gold", "min_compliance": 100.0, "required_checks": []},
            {"name": "silver", "min_compliance": 50.0, "required_checks": []},
        ]

        result = module.calculate_repository_rating(checks, ratings)
        assert result == "gold"

    def test_partial_passes_meets_lower_threshold(self) -> None:
        """50% passing checks should match the 50% threshold rating."""
        checks = {
            "readme": {"result": "pass"},
            "codeowners": {"result": "fail"},
        }
        ratings = [
            {"name": "gold", "min_compliance": 100.0, "required_checks": []},
            {"name": "silver", "min_compliance": 50.0, "required_checks": []},
        ]

        result = module.calculate_repository_rating(checks, ratings)
        assert result == "silver"

    def test_required_checks_must_all_pass(self) -> None:
        """Missing a required check should result in non-compliant."""
        checks = {"readme": {"result": "pass"}}
        ratings = [
            {
                "name": "gold",
                "min_compliance": 100.0,
                "required_checks": ["codeowners"],
            },
        ]

        result = module.calculate_repository_rating(checks, ratings)
        assert result == "non-compliant"

    def test_empty_checks_still_evaluates(self) -> None:
        """Empty checks dict should be evaluated against ratings."""
        checks: dict = {}
        ratings = [
            {"name": "gold", "min_compliance": 0.0, "required_checks": []},
        ]

        result = module.calculate_repository_rating(checks, ratings)
        assert result == "gold"


# ---------------------------------------------------------------------------
# serialise_scorecard_criteria
# ---------------------------------------------------------------------------


class TestSerialiseScorecard:
    def test_returns_dict_keyed_by_name(self) -> None:
        """Should return dict with rating names as keys."""
        ratings = [
            {
                "name": "gold",
                "min_compliance": 90.0,
                "required_checks": ["readme"],
            }
        ]

        result = module.serialise_scorecard_criteria(ratings)

        assert isinstance(result, dict)
        assert "gold" in result
        assert result["gold"]["min_compliance"] == 90.0
