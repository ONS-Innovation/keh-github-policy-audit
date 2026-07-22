"""Tests for structured logging utilities."""

import json
import logging
from unittest.mock import patch

from utils.structured_logging import (
    log_error,
    log_info,
    log_warning,
)


class TestSerialisePayload:
    def test_compact_json_when_pretty_disabled(self) -> None:
        """Should produce compact JSON when LOG_PRETTY_JSON is false or not set."""
        logger = logging.getLogger("test")

        with patch.object(logger, "info") as mock_log:
            log_info(logger, "test_event", key1="value1", key2=123)

        # Verify the logged payload is compact JSON
        logged_payload = mock_log.call_args[0][0]
        parsed = json.loads(logged_payload)

        assert parsed == {"event": "test_event", "key1": "value1", "key2": 123}
        # Compact JSON has no spaces after separators
        assert ", " not in logged_payload or ": " not in logged_payload

    def test_pretty_json_when_pretty_enabled(self) -> None:
        """Should produce pretty-printed JSON when LOG_PRETTY_JSON is true."""
        logger = logging.getLogger("test")

        with patch.dict("os.environ", {"LOG_PRETTY_JSON": "true"}):
            with patch.object(logger, "info") as mock_log:
                log_info(logger, "test_event", key1="value1", key2=123)

        # Verify the logged payload is pretty-printed JSON
        logged_payload = mock_log.call_args[0][0]
        parsed = json.loads(logged_payload)

        assert parsed == {"event": "test_event", "key1": "value1", "key2": 123}
        # Pretty JSON has indentation (contains newlines)
        assert "\n" in logged_payload

    def test_pretty_json_with_case_insensitive_check(self) -> None:
        """LOG_PRETTY_JSON should be case-insensitive."""
        logger = logging.getLogger("test")

        for env_value in ["TRUE", "True", "TrUe"]:
            with patch.dict("os.environ", {"LOG_PRETTY_JSON": env_value}):
                with patch.object(logger, "info") as mock_log:
                    log_info(logger, "test_event", field="value")

            logged_payload = mock_log.call_args[0][0]
            assert "\n" in logged_payload, f"Failed for LOG_PRETTY_JSON={env_value}"

    def test_compact_json_with_whitespace_in_env_var(self) -> None:
        """Should handle whitespace in LOG_PRETTY_JSON value."""
        logger = logging.getLogger("test")

        with patch.dict("os.environ", {"LOG_PRETTY_JSON": "  false  "}):
            with patch.object(logger, "info") as mock_log:
                log_info(logger, "test_event", field="value")

        logged_payload = mock_log.call_args[0][0]
        # Should be compact (no newlines from pretty printing)
        assert "\n" not in logged_payload

    def test_uses_extra_fields_in_lambda_json_mode(self) -> None:
        """Lambda JSON mode should avoid embedding JSON in message."""
        logger = logging.getLogger("test")

        with patch.dict("os.environ", {"APP_LOG_FORMAT": "JSON"}):
            with patch.object(logger, "info") as mock_log:
                log_info(
                    logger,
                    "github_rate_limit_checkpoint",
                    checkpoint="rate-limit-end",
                    remaining=123,
                )

        mock_log.assert_called_once_with(
            "github_rate_limit_checkpoint",
            extra={"checkpoint": "rate-limit-end", "remaining": 123},
        )

    def test_normalises_nested_fields_in_lambda_json_mode(self) -> None:
        """Nested and non-primitive fields should be JSON-safe in Lambda mode."""
        logger = logging.getLogger("test")

        class CustomObj:
            def __str__(self) -> str:
                return "custom-value"

        with patch.dict("os.environ", {"APP_LOG_FORMAT": "JSON"}):
            with patch.object(logger, "info") as mock_log:
                log_info(
                    logger,
                    "test_event",
                    payload={"a": 1, "b": [CustomObj(), None]},
                )

        mock_log.assert_called_once_with(
            "test_event", extra={"payload": {"a": 1, "b": ["custom-value", None]}}
        )

    def test_remaps_reserved_logrecord_fields_in_lambda_json_mode(self) -> None:
        """Reserved LogRecord keys should be remapped to avoid KeyError."""
        logger = logging.getLogger("test")

        with patch.dict("os.environ", {"APP_LOG_FORMAT": "JSON"}):
            with patch.object(logger, "info") as mock_log:
                log_info(logger, "lambda_invoked", module="utils.lambda_handler")

        mock_log.assert_called_once_with(
            "lambda_invoked", extra={"field_module": "utils.lambda_handler"}
        )

    def test_handles_reserved_key_collision_after_remap(self) -> None:
        """Remapped keys should remain unique when both forms are supplied."""
        logger = logging.getLogger("test")

        with patch.dict("os.environ", {"APP_LOG_FORMAT": "JSON"}):
            with patch.object(logger, "info") as mock_log:
                log_info(logger, "test_event", module="a", field_module="b")

        mock_log.assert_called_once_with(
            "test_event", extra={"field_module": "a", "field_module_2": "b"}
        )


class TestLogInfo:
    def test_logs_info_with_event_and_fields(self) -> None:
        """log_info should serialize event and fields as JSON."""
        logger = logging.getLogger("test")

        with patch.object(logger, "info") as mock_log:
            log_info(logger, "user_action", user_id=42, action="login")

        mock_log.assert_called_once()
        payload = json.loads(mock_log.call_args[0][0])
        assert payload == {"event": "user_action", "user_id": 42, "action": "login"}

    def test_log_info_handles_non_primitive_types(self) -> None:
        """log_info should handle non-primitive types with str() conversion."""
        logger = logging.getLogger("test")

        class CustomObj:
            def __str__(self):
                return "custom_value"

        with patch.object(logger, "info") as mock_log:
            log_info(logger, "custom_event", obj=CustomObj())

        payload = json.loads(mock_log.call_args[0][0])
        assert payload["obj"] == "custom_value"


class TestLogWarning:
    def test_logs_warning_with_event_and_fields(self) -> None:
        """log_warning should serialize event and fields as JSON."""
        logger = logging.getLogger("test")

        with patch.object(logger, "warning") as mock_log:
            log_warning(logger, "retry_attempt", attempt=2, max_attempts=3)

        mock_log.assert_called_once()
        payload = json.loads(mock_log.call_args[0][0])
        assert payload == {
            "event": "retry_attempt",
            "attempt": 2,
            "max_attempts": 3,
        }

    def test_logs_lambda_json_mode_with_extra_fields(self) -> None:
        """log_warning should use message + extra in Lambda JSON mode."""
        logger = logging.getLogger("test")

        with patch.dict("os.environ", {"APP_LOG_FORMAT": "JSON"}):
            with patch.object(logger, "warning") as mock_log:
                log_warning(logger, "retry_attempt", attempt=2, max_attempts=3)

        mock_log.assert_called_once_with(
            "retry_attempt", extra={"attempt": 2, "max_attempts": 3}
        )


class TestLogError:
    def test_logs_error_with_event_and_fields(self) -> None:
        """log_error should serialize event and fields as JSON."""
        logger = logging.getLogger("test")

        with patch.object(logger, "error") as mock_log:
            log_error(logger, "auth_failed", reason="invalid_token", status_code=401)

        mock_log.assert_called_once()
        payload = json.loads(mock_log.call_args[0][0])
        assert payload == {
            "event": "auth_failed",
            "reason": "invalid_token",
            "status_code": 401,
        }

    def test_logs_lambda_json_mode_with_extra_fields(self) -> None:
        """log_error should use message + extra in Lambda JSON mode."""
        logger = logging.getLogger("test")

        with patch.dict("os.environ", {"APP_LOG_FORMAT": "JSON"}):
            with patch.object(logger, "error") as mock_log:
                log_error(
                    logger,
                    "auth_failed",
                    reason="invalid_token",
                    status_code=401,
                )

        mock_log.assert_called_once_with(
            "auth_failed", extra={"reason": "invalid_token", "status_code": 401}
        )

    def test_app_log_format_overrides_runtime_fallback(self) -> None:
        """APP_LOG_FORMAT should take precedence over AWS runtime fallback variable."""
        logger = logging.getLogger("test")

        with patch.dict(
            "os.environ",
            {
                "APP_LOG_FORMAT": "TEXT",
                "AWS_LAMBDA_LOG_FORMAT": "JSON",
            },
        ):
            with patch.object(logger, "info") as mock_log:
                log_info(logger, "test_event", field="value")

        # TEXT mode keeps the JSON payload in the message string.
        payload = json.loads(mock_log.call_args[0][0])
        assert payload == {"event": "test_event", "field": "value"}
