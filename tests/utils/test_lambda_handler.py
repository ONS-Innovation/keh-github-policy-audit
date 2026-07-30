"""Tests for shared Lambda handler utilities."""

from typing import Any
from unittest.mock import patch

import pytest

from utils import lambda_handler


class TestGithubHandler:
    def test_wraps_lambda_with_client_setup(self) -> None:
        """The decorator should inject the GitHub client into the wrapped handler."""
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
        ):
            result = fake_handler(
                {"owner": "ONS-Innovation", "repository_name": "repo"},
                "ctx",
            )

        assert result == {"status": "PASS"}
        mock_client.assert_called_once_with("ONS-Innovation")

    def test_propagates_wrapped_handler_exceptions(self) -> None:
        """The decorator should not swallow exceptions from the wrapped handler."""
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
            pytest.raises(RuntimeError, match="boom"),
        ):
            fake_handler({"owner": "ONS-Innovation"}, None)
