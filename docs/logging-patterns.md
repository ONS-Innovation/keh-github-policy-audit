# Logging Patterns

This project uses structured JSON logging in application code, with Lambda-level JSON log formatting in AWS.

## Objectives

- Keep logs machine-parseable for CloudWatch Logs Insights.
- Keep a consistent pattern across handlers.
- Avoid leaking sensitive values in logs.

## How Logging Is Produced

1. Application code produces logs through `utils/structured_logging.py`.
2. For local and plain-text runtimes, messages are emitted as JSON strings.
3. In AWS Lambda JSON log mode (`logging_config { log_format = "JSON" }`), the `message` is the event name and log fields are emitted as top-level JSON attributes.

The log mode selection is:

- `APP_LOG_FORMAT=JSON`: use Lambda compatible emission (`message` + `extra` fields).
- `APP_LOG_FORMAT=TEXT` (or unset outside Lambda): emit a JSON payload string in `message`.
- If `APP_LOG_FORMAT` is unset, the code falls back to `AWS_LAMBDA_LOG_FORMAT` (runtime-provided by AWS when available).

## Standard Event Shape

Use an event name plus flat fields:

```json
{
  "event": "lambda_completed",
  "owner": "ONS-Innovation",
  "repositories_count": 123
}
```

In Lambda JSON mode, this appears in CloudWatch like:

```json
{
  "timestamp": "2026-07-22T12:34:56.789Z",
  "level": "INFO",
  "message": "lambda_completed",
  "owner": "ONS-Innovation",
  "repositories_count": 123
}
```

## Event Naming Conventions

- Use lowercase snake_case for `event` values.
- Prefer lifecycle names such as:
  - `lambda_invoked`
  - `lambda_completed`
  - `storing_results`
  - `stored_results`
  - `github_rate_limit_checkpoint`
  - `github_client_initialisation_retry`

## Field Conventions

- Use stable key names (for example `owner`, `repository_name`, `run_id`).
- Keep values primitive where possible (`str`, `int`, `bool`).
- Avoid deeply nested objects unless required for diagnostics.
- Do not include secrets, private keys, tokens, or full credential payloads.

## Local Development Format

`LOG_PRETTY_JSON` controls message formatting:

- `false` (default): compact single-line JSON.
- `true`: pretty-printed multi-line JSON for readability.

Example:

```bash
export LOG_PRETTY_JSON=true
python github_policy_audit/run_handler.py functions.list_teams.handler '{"owner":"ONS-Innovation"}'
```

With PRETTY JSON enabled:

```json
{
  "event": "lambda_invoked",
  "event_keys": [
    "owner"
  ]
}
```

Without PRETTY JSON enabled:

```json
{"event":"lambda_invoked","event_keys":["owner"]}
```

This can help digest dense logs during local development.

For deployed Lambda environments, keep `LOG_PRETTY_JSON` unset or set to `false` to reduce log volume.
AWS CloudWatch Logs automatically formats JSON logs for readability.

## Usage Pattern In Handlers

```python
from utils.structured_logging import log_info

log_info(logger, "lambda_invoked", event_keys=sorted(event.keys()))
log_info(logger, "lambda_completed", owner=owner, repository_count=count)
```

## Error And Warning Pattern

- Use `log_warning(...)` for recoverable/retryable situations.
- Use `log_error(...)` for terminal failures before re-raising.
- Include context fields that help triage (`status`, `url`, `attempt`), but avoid sensitive data.
