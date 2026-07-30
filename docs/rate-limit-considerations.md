# GitHub API Rate Limit Considerations

## Why this matters

This project runs many GitHub API checks through a Step Functions workflow. For large organisations, repository fan-out and per-repository parallel checks can consume API quota quickly.

To reduce risk of rate-limit failures, the workflow combines:

- Concurrency controls in Step Functions (`MaxConcurrency` in the repository distributed map)
- Retry logic during GitHub client initialisation for transient/rate-limit responses
- Endpoint-scoped retries for GitHub App installation token creation (`/app/installations/*/access_tokens`) when transient 403 responses are returned
- Short-lived in-process GitHub client reuse in warm Lambda runtimes (default TTL: `300` seconds)
- Dedicated Step Functions checkpoint tasks (`rate-limit-start`, `rate-limit-end`) to capture org-wide boundary snapshots

## What is logged now

Rate-limit telemetry is recorded by dedicated checkpoint tasks in the workflow.
The `rate_limit` Lambda creates a structured log event when each checkpoint is collected:

```text
github_rate_limit_checkpoint checkpoint=<rate-limit-start|rate-limit-end> remaining=<n|unknown> limit=<n|unknown> reset=<epoch|unknown>
```

## Scope of this telemetry

- Applies only to the dedicated Step Functions checkpoint tasks.
- Adds two `/rate_limit` calls per workflow execution (start and end checkpoints).

## Workflow boundary checkpoints

The state machine invokes `functions.rate_limit.handler` twice:

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

All rate-limit logs are written to Lambda function log groups. You can filter for `github_rate_limit_checkpoint` to see checkpoint logs.

### What to look for

- If you see `remaining=unknown` or `reset=unknown`, inspect the `rate_limit` Lambda logs for checkpoint request failures.
- If you see `remaining=0` at a checkpoint, GitHub API quota has been exhausted and workflow progress may be delayed until reset.
- If start-to-end checkpoint deltas are consistently high, reduce map concurrency or stagger schedules.
- Alongside the remaining quota, the `reset` timestamp can be used to estimate when the next workflow run can be scheduled. This is given in epoch seconds.

## Tuning guidance

- Start conservatively with low map concurrency for large organisations.
- Increase concurrency gradually while observing checkpoint deltas.
- If transient token-creation failures appear, keep map concurrency stable and tune `GITHUB_CLIENT_CACHE_TTL_SECONDS` before increasing throughput.
- Prefer predictable schedules that avoid overlapping organisation runs.
- If you have multiple workflows that run concurrently, consider staggering their schedules to avoid simultaneous API calls.
- Keep an eye on the rate-limit logs during testing and adjust concurrency as needed to avoid hitting the limit.

## Client initialisation resilience

- GitHub client initialisation retries transient failures with exponential backoff (`0.5s`, `1.0s`, `2.0s`) and bounded jitter.
- Plain 403 responses still fail fast by default, except for GitHub App installation token creation endpoint responses, which are retried because GitHub can return burst-protection 403s without explicit rate-limit headers.
- Warm Lambda runtimes reuse an in-memory GitHub client per owner for `GITHUB_CLIENT_CACHE_TTL_SECONDS` (default `300`) to reduce repeated token creation spikes.
