"""Helpers for consistent structured log messages."""

import json
import logging
import os
from typing import Any


_RESERVED_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys()) | {
    "message",
    "asctime",
}


def _lambda_json_logging_enabled() -> bool:
    configured_log_format = os.getenv("APP_LOG_FORMAT", "").strip().upper()
    if configured_log_format:
        return configured_log_format == "JSON"

    # Fallback for Lambda runtime auto-injected value when advanced logging
    # controls are enabled.
    return os.getenv("AWS_LAMBDA_LOG_FORMAT", "").strip().upper() == "JSON"


def _pretty_json_enabled() -> bool:
    return os.getenv("LOG_PRETTY_JSON", "false").strip().lower() == "true"


def _normalise_field_value(value: Any) -> Any:
    """Convert values into JSON-safe primitives for structured logging."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, dict):
        return {str(key): _normalise_field_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_normalise_field_value(item) for item in value]

    return str(value)


def _normalise_extra_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Return LogRecord-safe extra fields for logging APIs.

    Python logging rejects keys in `extra` that overwrite LogRecord attributes.
    This remaps reserved keys with a `field_` prefix.
    """
    normalised: dict[str, Any] = {}
    for key, value in fields.items():
        safe_key = str(key)
        if safe_key in _RESERVED_LOG_RECORD_FIELDS:
            safe_key = f"field_{safe_key}"

        # Avoid accidental collisions after remapping.
        suffix = 2
        unique_key = safe_key
        while unique_key in normalised:
            unique_key = f"{safe_key}_{suffix}"
            suffix += 1

        normalised[unique_key] = _normalise_field_value(value)

    return normalised


def _serialise_payload(event: str, fields: dict[str, Any]) -> str:
    payload = {"event": event, **_normalise_field_value(fields)}
    if _pretty_json_enabled():
        return json.dumps(payload, default=str, indent=2, sort_keys=True)
    return json.dumps(payload, default=str, separators=(",", ":"), sort_keys=True)


def _log(
    logger: logging.Logger, level: str, event: str, fields: dict[str, Any]
) -> None:
    """Emit logs in a shape compatible with both local and Lambda JSON logging."""
    if _lambda_json_logging_enabled():
        # In Lambda JSON mode, message becomes the event name and `extra`
        # fields are emitted as top-level JSON attributes by AWS logging.
        getattr(logger, level)(event, extra=_normalise_extra_fields(fields))
        return

    getattr(logger, level)(_serialise_payload(event, fields))


def log_info(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log an info message as a compact JSON payload."""
    _log(logger, "info", event, fields)


def log_warning(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log a warning message as a compact JSON payload."""
    _log(logger, "warning", event, fields)


def log_error(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log an error message as a compact JSON payload."""
    _log(logger, "error", event, fields)
