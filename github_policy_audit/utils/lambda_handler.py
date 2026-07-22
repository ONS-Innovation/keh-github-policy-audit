"""Shared Lambda handler utilities."""

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from policy_methods_library.github.clients import GitHubRestClient

from utils import github


P = ParamSpec("P")
R = TypeVar("R")


def github_handler(
    func: Callable[Concatenate[dict[str, Any], Any, GitHubRestClient, P], R],
) -> Callable[Concatenate[dict[str, Any], Any, P], R]:
    """Wrap a Lambda handler with GitHub client setup and rate-limit logging."""

    @wraps(func)
    def wrapper(
        event: dict[str, Any], context: Any, *args: P.args, **kwargs: P.kwargs
    ) -> R:
        handler_logger = logging.getLogger(func.__module__)
        handler_logger.info("Lambda invoked with event keys=%s", sorted(event.keys()))

        client = github.get_github_client(event["owner"])
        step_name = func.__module__
        github.log_step_rate_limit(client, "start", step_name)
        try:
            return func(event, context, client, *args, **kwargs)
        finally:
            github.log_step_rate_limit(client, "end", step_name)

    return wrapper
