"""Unit tests for the rate_limit Lambda handler."""

import importlib
from unittest.mock import patch

import pytest


class TestRateLimitHandler:
    module = importlib.import_module("functions.rate_limit.handler")

    def test_returns_rate_limit_payload_for_checkpoint(self):
        """The handler should return checkpoint metadata and parsed core rate-limit values."""

        class FakeClient:
            def make_request(self, method, path):
                assert method == "GET"
                assert path == "/rate_limit"
                return {
                    "resources": {
                        "core": {
                            "limit": 5000,
                            "remaining": 4988,
                            "reset": 1721668800,
                            "used": 12,
                        }
                    }
                }

        event = {
            "owner": "ONS-Innovation",
            "checkpoint": "rate-limit-start",
        }

        with patch.object(self.module, "get_github_client", return_value=FakeClient()):
            result = self.module.handler(event, None)

        assert result["checkpoint"] == "rate-limit-start"
        assert result["limit"] == 5000
        assert result["remaining"] == 4988
        assert result["reset"] == 1721668800
        assert result["used"] == 12
        assert "retrieved_at" in result

    def test_raises_for_missing_owner(self):
        """A missing owner key should raise a KeyError."""
        with pytest.raises(KeyError, match="owner"):
            self.module.handler({"checkpoint": "rate-limit-end"}, None)

    def test_raises_for_invalid_checkpoint(self):
        """The handler should validate checkpoint values."""
        with pytest.raises(ValueError, match="checkpoint"):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "checkpoint": "middle",
                },
                None,
            )

    def test_raises_for_invalid_rate_limit_payload_shape(self):
        """The handler should fail when /rate_limit response is missing resources.core."""

        class FakeClient:
            def make_request(self, method, path):
                assert method == "GET"
                assert path == "/rate_limit"
                return {"resources": {}}

        with (
            patch.object(self.module, "get_github_client", return_value=FakeClient()),
            pytest.raises(ValueError, match="resources.core"),
        ):
            self.module.handler(
                {
                    "owner": "ONS-Innovation",
                    "checkpoint": "rate-limit-end",
                },
                None,
            )
