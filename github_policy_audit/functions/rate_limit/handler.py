"""Lambda handler to fetch current GitHub API rate-limit details."""

import logging
from datetime import datetime, timezone
from typing import Any

from utils.github import get_github_client
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _extract_core_rate_limit(rate_limit_payload: Any) -> dict[str, Any]:
    """Return the core rate-limit object from a /rate_limit response payload."""
    if hasattr(rate_limit_payload, "json") and callable(rate_limit_payload.json):
        rate_limit_payload = rate_limit_payload.json()

    if not isinstance(rate_limit_payload, dict):
        raise ValueError("GitHub /rate_limit response must be a dictionary")

    resources = rate_limit_payload.get("resources")
    if not isinstance(resources, dict):
        raise ValueError("GitHub /rate_limit response missing resources")

    core = resources.get("core")
    if not isinstance(core, dict):
        raise ValueError("GitHub /rate_limit response missing resources.core")

    return core


def handler(event, context):
    """Step Function invokes with {"owner": "...", "checkpoint": "rate-limit-start|rate-limit-end"}."""
    del context

    owner = event["owner"]
    checkpoint = event.get("checkpoint")

    if checkpoint not in {"rate-limit-start", "rate-limit-end"}:
        raise ValueError("checkpoint must be one of: rate-limit-start, rate-limit-end")

    client = get_github_client(owner)
    core_rate_limit = _extract_core_rate_limit(
        client.make_request("GET", "/rate_limit")
    )

    rate_limit = {
        "checkpoint": checkpoint,
        "limit": core_rate_limit.get("limit"),
        "remaining": core_rate_limit.get("remaining"),
        "reset": core_rate_limit.get("reset"),
        "used": core_rate_limit.get("used"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }

    log_info(
        logger,
        "github_rate_limit_checkpoint",
        owner=owner,
        checkpoint=checkpoint,
        remaining=rate_limit["remaining"],
        limit=rate_limit["limit"],
        reset=rate_limit["reset"],
    )

    return rate_limit
