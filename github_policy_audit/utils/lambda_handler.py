"""Shared Lambda handler utilities."""

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from policy_methods_library.github.clients import GitHubRestClient

from utils import github
from utils.structured_logging import log_info


P = ParamSpec("P")
R = TypeVar("R")


def github_handler(
    func: Callable[Concatenate[dict[str, Any], Any, GitHubRestClient, P], R],
) -> Callable[Concatenate[dict[str, Any], Any, P], R]:
    """Wrap a Lambda handler with GitHub client setup and invocation logging."""

    @wraps(func)
    def wrapper(
        event: dict[str, Any], context: Any, *args: P.args, **kwargs: P.kwargs
    ) -> R:
        handler_logger = logging.getLogger(func.__module__)
        log_info(
            handler_logger,
            "lambda_invoked",
            handler_module=func.__module__,
            event_keys=sorted(event.keys()),
        )

        client = github.get_github_client(event["owner"])
        return func(event, context, client, *args, **kwargs)

    return wrapper


def fail_on_error_result(result: dict[str, Any], check_name: str) -> None:
    """Raise when a policy check explicitly reports an error result."""
    if str(result.get("result", "")).lower() != "error":
        return

    error_detail = (
        result.get("message") or result.get("details") or "No details provided"
    )
    raise RuntimeError(f"Policy check '{check_name}' returned an error: {error_detail}")
