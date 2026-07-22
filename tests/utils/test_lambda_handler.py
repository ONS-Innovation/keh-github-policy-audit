"""Tests for shared Lambda handler utilities."""

from typing import Any
from unittest.mock import patch

import pytest

from utils import lambda_handler


class TestGithubHandler:
    def test_wraps_lambda_with_client_setup_and_rate_limit_logging(self) -> None:
        """The decorator should inject the GitHub client and log both rate-limit phases."""
        client = object()

        @lambda_handler.github_handler
        def fake_handler(
            event: dict[str, Any], context: object, injected_client: object
        ):
            assert event == {"owner": "ONS-Innovation", "repository_name": "repo"}
            assert context == "ctx"
            assert injected_client is client
            return {"status": "PASS"}

        with (
            patch.object(
                lambda_handler.github,
                "get_github_client",
                return_value=client,
            ) as mock_client,
            patch.object(
                lambda_handler.github, "log_step_rate_limit"
            ) as mock_rate_limit,
        ):
            result = fake_handler(
                {"owner": "ONS-Innovation", "repository_name": "repo"},
                "ctx",
            )

        assert result == {"status": "PASS"}
        mock_client.assert_called_once_with("ONS-Innovation")
        assert mock_rate_limit.call_args_list == [
            ((client, "start", fake_handler.__module__),),
            ((client, "end", fake_handler.__module__),),
        ]

    def test_logs_end_rate_limit_when_wrapped_handler_raises(self) -> None:
        """The decorator should still emit the end-phase rate-limit log on failure."""
        client = object()

        @lambda_handler.github_handler
        def fake_handler(
            event: dict[str, Any], context: object, injected_client: object
        ):
            del event, context
            assert injected_client is client
            raise RuntimeError("boom")

        with (
            patch.object(
                lambda_handler.github, "get_github_client", return_value=client
            ),
            patch.object(
                lambda_handler.github, "log_step_rate_limit"
            ) as mock_rate_limit,
            pytest.raises(RuntimeError, match="boom"),
        ):
            fake_handler({"owner": "ONS-Innovation"}, None)

        assert mock_rate_limit.call_args_list == [
            ((client, "start", fake_handler.__module__),),
            ((client, "end", fake_handler.__module__),),
        ]
