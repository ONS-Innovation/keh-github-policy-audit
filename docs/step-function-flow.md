# Step Function Flow — GitHub Policy Audit

## Overview

The Step Function is triggered weekly by an EventBridge schedule and orchestrates all Lambda functions to audit GitHub organisation policy compliance, then store results in S3 using run-scoped prefixes.

**Trigger:** `cron(0 8 ? * MON *)` — every Monday at 08:00 UTC  
**Input:** `{"owner": "<org-name>", "levels": ["critical", "high", "medium", "low"]}`

## Flow

```mermaid
flowchart TD
    EB([EventBridge\nWeekly Schedule\ncron 0 8 MON]) -->|owner: org-name| SF_START([Start Execution])

    SF_START --> INIT_PARALLEL

    subgraph INIT_PARALLEL[" Parallel — Initialise "]
        LR[list_repositories]
        LT[list_teams]
    end

    INIT_PARALLEL --> PREP[PrepareInput\nset run_id + output_bucket]
    PREP --> ORG_PARALLEL

    subgraph ORG_PARALLEL[" Parallel — Organisation Checks "]
        DS[dependabot_slo]
        SS[secret_scanning_slo]
        TM_MAP["Map over teams → team_maintainer"]
    end

    ORG_PARALLEL --> REPO_MAP

    subgraph REPO_MAP[" Distributed Map over repositories\nMaxConcurrency = 5 "]
        subgraph REPO_PARALLEL[" Parallel — Per-repository Checks "]
            RC1[codeowners]
            RC2[dependabot]
            RC3[external_pull_request]
            RC4[gitignore]
            RC5[inactivity]
            RC6[license]
            RC7[naming_convention]
            RC8[pirr]
            RC9[readme]
            RC10[repository_access]
            RC11[security_scanning]
        end
        REPO_WRITE[store_repository_output\nwrite audit-runs owner/run_id/repositories/repo.json]
        REPO_PARALLEL --> REPO_WRITE
    end

    REPO_MAP --> STORE[store_output\naggregate run prefix and write audit-results owner/run_id.json]
    STORE --> END([End])
```

## Stage Summary

| Stage               | State Type                                                | Lambdas                                                                                                                                                                    |
| ------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Initialise          | `Parallel`                                                | `list_repositories`, `list_teams`                                                                                                                                          |
| Prepare input       | `Pass`                                                    | None (injects `run_id` and `output_bucket`)                                                                                                                                |
| Organisation checks | `Parallel` + inner `Map` for teams                        | `dependabot_slo`, `secret_scanning_slo`, `team_maintainer`                                                                                                                 |
| Repository checks   | `Map` (Mode=`DISTRIBUTED`, MaxConcurrency=5) + `Parallel` | `codeowners`, `dependabot`, `external_pull_request`, `gitignore`, `inactivity`, `license`, `naming_convention`, `pirr`, `readme`, `repository_access`, `security_scanning` |
| Repo output write   | `Task`                                                    | `store_repository_output`                                                                                                                                                  |
| Final aggregation   | `Task`                                                    | `store_output`                                                                                                                                                             |

## Storage and Lifecycle

Repository-level artifacts are written to:

- `audit-runs/<owner>/<run_id>/repositories/<repository>.json`

Final run summary is written to:

- `audit-results/<owner>/<run_id>.json`

S3 lifecycle rules manage growth:

- `audit-runs/` uses short retention (`audit_run_retention_days`, default 30).
- `audit-results/` uses longer retention (`audit_summary_retention_days`, default 365).

## Rate Limit and State Size Considerations

The repository checks map uses `Mode = DISTRIBUTED` and `MaxConcurrency = 5` (configurable) to limit simultaneous GitHub API calls and stay within rate limits.

The 11 per-repository checks run in parallel within each repository item, but Step Functions state remains small because repository check outputs are persisted to S3 and discarded from parent execution state after each item.

## Data Flow

### 1. EventBridge → Initialise

EventBridge injects the initial execution input:

```json
{
    "owner": "ONS-Innovation",
    "levels": ["critical", "high", "medium", "low"]
}
```

The `Initialise` parallel state fans out to `list_repositories` and `list_teams`, each receiving only `owner` and `levels` from the parent state.

`list_repositories` returns only non-archived repositories.

### 2. Initialise → PrepareInput

The parallel branches return their results as an array under `$.initial_data`:

```json
{
    "owner": "ONS-Innovation",
    "levels": ["critical", "high", "medium", "low"],
    "initial_data": [
        [{ "name": "repo-a", "data": { "updated_at": "...", "security_and_analysis": {} } }],
        [{ "name": "team-a", "slug": "team-a" }]
    ]
}
```

### 3. PrepareInput → OrganisationChecks

The `PrepareInput` pass state reshapes the input, injecting `run_id` (from the execution name) and `output_bucket`, and promoting `initial_data[0]` and `initial_data[1]` to `repositories` and `teams`, respectively. This data structure is used by all downstream stages:

```json
{
    "owner": "ONS-Innovation",
    "levels": ["critical", "high", "medium", "low"],
    "run_id": "<sfn-execution-name>",
    "output_bucket": "<s3-bucket-name>",
    "repositories": [{ "name": "repo-a", "data": { "updated_at": "...", "security_and_analysis": {} } }],
    "teams": [{ "name": "team-a", "slug": "team-a" }]
}
```

### 4. OrganisationChecks

Three branches run in parallel. Each branch receives a subset of the state:

| Branch | Receives |
| --- | --- |
| `dependabot_slo` | `owner`, `levels` |
| `secret_scanning_slo` | `owner` |
| `TeamMaintainerMap` (Map over `teams`) | `owner`, `team.slug` per iteration |

Their combined outputs are collected into `$.organisation_results` as a three-element array — one element per branch, in declaration order:

```json
{
    "organisation_results": [
        { "check_name": "dependabot_slo",    "result": "pass", "message": "..." },
        { "check_name": "secret_scanning_slo", "result": "pass", "message": "..." },
        [
            { "check_name": "team_maintainer", "result": "pass", "message": "..." }
        ]
    ]
}
```

All other top-level keys (`owner`, `levels`, `run_id`, `output_bucket`, `repositories`, `teams`) are preserved unchanged.

### 5. RepositoryChecksMap (Distributed Map)

Each item in `$.repositories` spawns a child execution. The item selector passes only what each child needs:

```json
{
    "owner": "ONS-Innovation",
    "run_id": "<sfn-execution-name>",
    "output_bucket": "<s3-bucket-name>",
    "repository": { "name": "repo-a", "data": { "updated_at": "...", "security_and_analysis": {} } }
}
```

Inside each child execution, 11 repository check Lambdas run in parallel. Each check Lambda receives `owner`, `repository_name`, and `data`, and returns:

```json
{ "check_name": "readme", "result": "pass", "message": "README exists" }
```

The `ResultSelector` on each check task strips any additional fields, retaining only `check_name`, `result`, and `message`. The `RepositoryChecksParallel` state collects all 11 results into `$.check_results`.

`FormatRepositoryChecks` then assembles the write payload:

```json
{
    "owner": "ONS-Innovation",
    "run_id": "<sfn-execution-name>",
    "output_bucket": "<s3-bucket-name>",
    "repository_name": "repo-a",
    "checks": [
        { "check_name": "readme",      "result": "pass", "message": "..." },
        { "check_name": "codeowners",  "result": "fail", "message": "..." }
    ]
}
```

#### S3 write - per repository

`store_repository_output` writes this payload to S3 and returns nothing to the parent state (`ResultPath: null`):

```bash
s3://<bucket>/audit-runs/<owner>/<run_id>/repositories/<repository_name>.json
```

The parent map's `ResultPath` is also `null`, so no repository data accumulates in the parent execution state.

> This write is **crucial** for scaling since the step function state size is too small to handle all repository check results in memory. Each child execution writes its results to S3 and discards them from state, allowing the parent execution to continue without exceeding the 256KB state limit.

### 6. store_output (Final Aggregation)

After all repository child executions complete, `store_output` is invoked with only the organisation-level data still held in state:

```json
{
    "owner": "ONS-Innovation",
    "run_id": "<sfn-execution-name>",
    "output_bucket": "<s3-bucket-name>",
    "teams": [{ "name": "team-a", "slug": "team-a" }],
    "organisation_results": [ ... ],
    "team_results": [ ... ]
}
```

The Lambda lists all objects under `audit-runs/<owner>/<run_id>/repositories/`, reads each file, and builds the aggregated output.

#### S3 write — final summary

```bash
s3://<bucket>/audit-results/<owner>/<run_id>.json
```

The summary file structure:

```json
{
    "owner": "ONS-Innovation",
    "repositories": {
        "repo-a": { "readme": { "check_name": "readme", "result": "pass", "message": "..." } }
    },
    "organisation_checks": {
        "dependabot_slo": { "check_name": "dependabot_slo", "result": "pass", "message": "..." }
    },
    "teams": {
        "team-a": { "team_maintainer": { "check_name": "team_maintainer", "result": "pass", "message": "..." } }
    },
    "summary": {
        "total_repositories": 1,
        "compliant_repositories": 1,
        "total_teams": 1,
        "compliant_teams": 1,
        "repository_checks": { "readme": { "total": 1, "compliant": 1 } },
        "organisation_checks": { "dependabot_slo": { "compliant": true } }
    },
    "timestamp": "2026-07-16T08:00:00+00:00"
}
```
