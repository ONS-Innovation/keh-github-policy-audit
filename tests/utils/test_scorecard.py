"""Unit tests for scorecard utility functions."""

import importlib

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
