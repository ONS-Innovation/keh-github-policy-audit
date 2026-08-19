# GitHub API Rate Limit Considerations

## Why this matters

This project runs many GitHub API checks through a Step Functions workflow. For large organisations, repository fan-out and per-repository parallel checks can consume API quota quickly.

To reduce risk of rate-limit failures, the workflow combines:

- Concurrency controls in Step Functions (`MaxConcurrency` in the repository distributed map)
- Retry logic during GitHub client initialisation for transient/rate-limit responses
- Endpoint-scoped retries for GitHub App installation token creation (`/app/installations/*/access_tokens`) when transient 403 responses are returned
- Two-tier Step Functions retry policy on every Task state (see [Step Functions retry policy](#step-functions-retry-policy))
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

## Step Functions retry policy

Every Task state in the state machine uses a two-tier retry policy. Retrying in Step Functions rather than sleeping inside Lambda avoids blocking an execution slot (and incurring Lambda duration cost) during the wait.

**Tier 1 — fast, infra errors** (`IntervalSeconds: 2`, `BackoffRate: 2`, `MaxAttempts: 3`):

Covers transient AWS-side failures that resolve quickly:

- `Lambda.ServiceException`
- `Lambda.SdkClientException`
- `Lambda.TooManyRequestsException`

**Tier 2 — slow, application errors** (`IntervalSeconds: 60`, `BackoffRate: 2`, `MaxAttempts: 3`, `JitterStrategy: FULL`):

Covers Lambda execution failures including secondary rate-limit responses from GitHub, which require waiting at least one minute before retrying. Uses full jitter to spread retries across concurrent executions:

- `Lambda.AWSLambdaException`
- `States.TaskFailed`

States that only write to S3 (`store_output`, `store_repository_output`) use tier 1 only — they do not call the GitHub API.

## Secondary rate limit retries

GitHub enforces a secondary rate limit (distinct from the primary quota) that caps the number of requests to a single endpoint per minute. At scale — for example, checking 1,000 repositories in a fan-out — this limit can be reached even when the primary quota (`X-RateLimit-Remaining`) is non-zero. GitHub returns a `403` with a body containing `"abuse detection mechanism"` or `"rate limit"`, or a `429`.

Lambdas fail fast on these responses. The Step Functions slow retry tier (60s base, FULL jitter) then waits before re-invoking the Lambda, matching [GitHub's documented guidance](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api#exceeding-the-rate-limit) to wait at least one minute.

This was introduced after a secondary rate-limit `403` was observed in production at ~993 repositories checked on the `/repos/{owner}/{repo}/branches` endpoint.
