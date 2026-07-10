# Step Function Flow — GitHub Policy Audit

## Overview

The Step Function is triggered weekly by an EventBridge schedule and orchestrates all Lambda functions to audit GitHub organisation policy compliance, then store the results to S3.

**Trigger:** `cron(0 8 ? * MON *)` — every Monday at 08:00 UTC  
**Input:** `{"owner": "<org-name>"}`

## Flow

```mermaid
flowchart TD
    EB([EventBridge\nWeekly Schedule\ncron 0 8 MON]) -->|owner: org-name| SF_START([Start Execution])

    SF_START --> INIT_PARALLEL

    subgraph INIT_PARALLEL[" Parallel — Initialise "]
        LR[list_repositories]
        LT[list_teams]
    end

    INIT_PARALLEL --> ORG_PARALLEL

    subgraph ORG_PARALLEL[" Parallel — Organisation Checks "]
        DS[dependabot_slo]
        SS[secret_scanning_slo]
        TM_MAP["Map over teams → team_maintainer"]
    end

    ORG_PARALLEL --> REPO_MAP

    subgraph REPO_MAP[" Map over repositories\nMaxConcurrency = 5 "]
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
    end

    REPO_MAP --> STORE[store_output\nwrites JSON to S3]
    STORE --> END([End])
```

## Stage Summary

| Stage | State Type | Lambdas |
| --- | --- | --- |
| Initialise | `Parallel` | `list_repositories`, `list_teams` |
| Organisation checks | `Parallel` + inner `Map` for teams | `dependabot_slo`, `secret_scanning_slo`, `team_maintainer` |
| Repository checks | `Map` (MaxConcurrency=5) → inner `Parallel` | `codeowners`, `dependabot`, `external_pull_request`, `gitignore`, `inactivity`, `license`, `naming_convention`, `pirr`, `readme`, `repository_access`, `security_scanning` |
| Store output | `Task` | `store_output` |

## Rate Limit Considerations

The repository checks `Map` state uses `MaxConcurrency = 5` (configurable) to limit simultaneous GitHub API calls and stay within rate limits. The 11 per-repository checks run in parallel **within** each Map iteration, but since they target different API endpoints this is low risk.
