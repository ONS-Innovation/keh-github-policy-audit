# GitHub API Rate Limit Considerations

## Why this matters

This project runs many GitHub API checks through a Step Functions workflow. For large organisations, repository fan-out and per-repository parallel checks can consume API quota quickly.

To reduce risk of rate-limit failures, the workflow combines:

- Concurrency controls in Step Functions (`MaxConcurrency` in the repository distributed map)
- Retry logic during GitHub client initialisation for transient/rate-limit responses
- Explicit rate-limit telemetry at the start and end of each GitHub-backed step
- Dedicated Step Functions checkpoint tasks (`rate-limit-start`, `rate-limit-end`) to capture org-wide boundary snapshots

## What is logged now

Every Lambda step that uses the shared GitHub client logs the remaining rate limit at two points:

- `phase=start`: immediately after the GitHub client is created
- `phase=end`: immediately before the handler returns

The log format is:

```text
GitHub rate limit step=<step_module> phase=<start|end> remaining=<n|unknown> reset=<epoch|unknown>
```

If the `/rate_limit` call itself fails, the step does not fail because of telemetry. Instead, a warning is logged:

```text
Unable to read GitHub rate limit step=<step_module> phase=<start|end> error=<...>
```

## Scope of this telemetry

- Applies to all GitHub-backed Step Function task handlers.
- Does not apply to storage-only handlers that do not call GitHub.
- Adds two extra GitHub API calls per GitHub-backed step invocation (one at start, one at end).

## Workflow boundary checkpoints

In addition to per-step logs, the state machine invokes `functions.rate_limit.handler` twice:

- Start checkpoint: immediately after `PrepareInitialInput` (`checkpoint=rate-limit-start`)
- End checkpoint: after repository checks complete, before final aggregation (`checkpoint=rate-limit-end`)

Each checkpoint returns a compact payload with `limit`, `remaining`, `reset`, `used`, and `retrieved_at`.
These are passed to `store_output` and written into both the final summary JSON and the terminal Step Functions output as:

- `rate-limit-start`
- `rate-limit-end`

This helps estimate the total API quota consumed by the workflow, and can be used to tune concurrency for large organisations.

## Using the logs

The Audit tool has 2 main areas of logs:

- the main Step Function execution log.
- the CloudWatch log group for each Lambda function.

All rate-limit logs are written to the Lambda function log group. You can filter for `GitHub rate limit` to see all rate-limit logs.

### What to look for

- If you see `remaining=unknown` or `reset=unknown`, the `/rate_limit` call failed. This is usually a transient error and can be ignored.
- If you see `remaining=0`, the GitHub API quota has been exhausted. The workflow will retry after the reset time, but this may cause delays in processing.
- If you see `remaining` consistently low (e.g., < 100) at the start of steps, this indicates that the workflow is consuming quota quickly and may need to be tuned.

## Tuning guidance

- Start conservatively with low map concurrency for large organisations.
- Increase concurrency gradually while observing rate-limit logs.
- Prefer predictable schedules that avoid overlapping organisation runs.
- If you have multiple workflows that run concurrently, consider staggering their schedules to avoid simultaneous API calls.
- Keep an eye on the rate-limit logs during testing and adjust concurrency as needed to avoid hitting the limit.
