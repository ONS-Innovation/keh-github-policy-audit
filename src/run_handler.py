"""Run Lambda-style check handlers locally.

Examples:
python src/run_handler.py functions.checks.codeowners.handler '{"owner":"ONS-Innovation","repository_name":"keh-github-policy-audit"}'
python src/run_handler.py functions.checks.codeowners.handler payload.json --event-file
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from typing import Any


def parse_event(event_arg: str, event_file: bool) -> dict[str, Any]:
    """Parse event payload from an inline JSON string or JSON file."""
    if event_file:
        with open(event_arg, "r", encoding="utf-8") as f:
            event = json.load(f)
    else:
        event = json.loads(event_arg)

    if not isinstance(event, dict):
        raise ValueError("Event payload must be a JSON object")
    return event


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Lambda-style handler locally")
    parser.add_argument(
        "module", help="Module path, e.g. functions.checks.codeowners.handler"
    )
    parser.add_argument(
        "event", help="Inline JSON event or file path with --event-file"
    )
    parser.add_argument(
        "--function", default="handler", help="Function name (default: handler)"
    )
    parser.add_argument(
        "--event-file",
        action="store_true",
        help="Treat event argument as a JSON file path",
    )
    args = parser.parse_args()

    try:
        event = parse_event(args.event, args.event_file)
        module = importlib.import_module(args.module)
        handler = getattr(module, args.function)
    except (
        json.JSONDecodeError,
        OSError,
        ValueError,
        ImportError,
        AttributeError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not callable(handler):
        print(f"Error: {args.module}.{args.function} is not callable", file=sys.stderr)
        return 1

    try:
        result = handler(event, None)
    except Exception as exc:  # pragma: no cover
        print(f"Handler raised an exception: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
