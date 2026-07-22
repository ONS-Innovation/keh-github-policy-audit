"""Helpers for consistent structured log messages."""

import json
import logging
import os
from typing import Any


def _pretty_json_enabled() -> bool:
    return os.getenv("LOG_PRETTY_JSON", "false").strip().lower() == "true"


def _serialise_payload(event: str, fields: dict[str, Any]) -> str:
    payload = {"event": event, **fields}
    if _pretty_json_enabled():
        return json.dumps(payload, default=str, indent=2, sort_keys=True)
    return json.dumps(payload, default=str, separators=(",", ":"), sort_keys=True)


def log_info(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log an info message as a compact JSON payload."""
    logger.info(_serialise_payload(event, fields))


def log_warning(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log a warning message as a compact JSON payload."""
    logger.warning(_serialise_payload(event, fields))


def log_error(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log an error message as a compact JSON payload."""
    logger.error(_serialise_payload(event, fields))
