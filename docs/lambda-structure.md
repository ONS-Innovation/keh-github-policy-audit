# Lambda Structure

This project uses a consistent Lambda layout so that each function stays small and focused:

- the handler module is responsible for the Lambda entry point, any processing and its response
- shared setup lives in utilities
- business logic lives in `policy_methods_library`

This keeps individual handlers easy to scan and reduces duplication across the audit workflow.

## Layout

All Lambda functions live in the `/functions` folder, organised by type and purpose:

- **General functions** (`functions/`): Not specific to a single check type
  - `list_repositories/` - Lists all repositories for an organisation
  - `list_teams/` - Lists all teams for an organisation
  - `rate_limit/` - GitHub API rate limit checkpoint

- **Check functions** (organised by entity type):
  - `organisation_checks/` - Organisation-level checks
  - `team_checks/` - Team-level checks
  - `repository_checks/` - Repository-level checks

- **Storage functions** (`storage_functions/`): Aggregation and persistence handlers
  - `store_output/` - Final aggregation across all results
  - `store_repository_output/` - Aggregates per-repository check results
  - `store_team_checks/` - Aggregates per-team check results
  - `store_organisation_checks/` - Stores organisation-level check results

When organising a new function, consider:

1. **Is it a check?** Does it run a specific policy check? Add it to the appropriate `*_checks/` folder (organisation, team, or repository).
2. **Is it an aggregator?** Does it aggregate multiple results? Add it to `storage_functions/`.
3. **Is it a general function?** Does it perform a task that is not a check or an aggregator? Add it to the `functions/` root.

This structure ensures:

- Clear separation of concerns
- Easy discovery of related functions
- Grouped test organization following the same structure

## Test Organisation

Tests mirror the function structure exactly for easy discovery. Each handler has a dedicated test file named `test_<handler_name>.py`:

```bash
tests/functions/
├── test_list_repositories.py         # General functions
├── test_list_teams.py
├── test_rate_limit.py
├── organisation_checks/
│   ├── test_dependabot_slo.py        # Organisation-level checks
│   └── test_secret_scanning_slo.py
├── repository_checks/
│   ├── test_branch_protection.py     # Repository-level checks
│   ├── test_codeowners.py
│   ├── test_dependabot.py
│   ├── ... (10 more repository checks)
├── storage_functions/
│   ├── test_store_output.py          # Storage aggregators
│   ├── test_store_repository_output.py
│   ├── test_store_team_checks.py
│   └── test_store_organisation_checks.py
└── team_checks/
    └── test_team_maintainer.py       # Team-level checks
```

When adding a new handler, also add a corresponding test file following this naming convention. This makes it immediately clear where tests for a specific handler can be found.

## Two Handler Shapes

Focusing on the lambdas themselves, there are two main shapes:

### GitHub-backed handlers

These handlers need a GitHub client and normally follow the same lifecycle:

1. Log the incoming event shape.
2. Build a GitHub client from the configured GitHub App secrets.
3. Log rate-limit state at the start and end of the step.
4. Call the policy or list function.
5. Return a compact, Step Functions-friendly payload.

That repeated process is now shared by `github_handler` in `utils/lambda_handler.py`.

Example:

```python
import logging

from policy_methods_library.checks.codeowners import check_codeowners
from utils.lambda_handler import github_handler
from utils.structured_logging import log_info


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    result = check_codeowners(client, event["repository_name"])
    result["check_name"] = "codeowners"
    log_info(
        logger,
        "lambda_completed",
        check=result["check_name"],
        result=result.get("result"),
    )
    return result
```

The decorated handler keeps the public Lambda shape as `handler(event, context)`, while the wrapped implementation receives the injected `client` as a third argument.

### Non-GitHub-backed handlers

Some handlers do not need a GitHub client. For example, naming convention checks only need repository metadata already present in the Step Functions input.

Those handlers should remain simple and undecorated.

Example:

```python
def handler(event, context):
    result = check_naming_convention(event["repository_name"])
    result["check_name"] = "naming_convention"
    return result
```

This also applies to any general functions that do not need a GitHub client, such as `store_output`.

## The `github_handler` Decorator

The decorator in `utils/lambda_handler.py` exists to remove repeated setup from handlers that depend on GitHub.

It currently does three things:

- logs the event keys at invocation time
- creates the GitHub client using `utils.github.get_github_client()`
- logs GitHub rate-limit state at the start and end of the handler

This keeps the handler focused on its specific check, while still providing consistent logging and telemetry across all GitHub-backed handlers.

## Aggregation Handlers

Some handlers aggregate results from multiple checks across entities (repositories, teams, etc.). These handlers receive arrays of check results and write them to S3.

### store_repository_output

Aggregates repository check results from all checks (12 checks per repository) into a single S3 file. Input format:

```python
{
    "owner": "org-name",
    "run_id": "sfn-execution-id",
    "repository_name": "repo-name",
    "output_bucket": "bucket-name",
    "checks": [
        {"check_name": "codeowners", "result": "pass", "message": "..."},
        {"check_name": "dependabot", "result": "fail", "message": "..."},
        # ...
    ]
}
```

### store_team_checks

Aggregates team check results (extensible, defined in `terraform/locals.tf` as `team_check_names`) into a single S3 file per team. Automatically normalizes check results from list to dictionary format keyed by check name. Input format:

```python
{
    "owner": "org-name",
    "run_id": "sfn-execution-id",
    "team_slug": "team-slug",
    "output_bucket": "bucket-name",
    "checks": [
        {"check_name": "team_maintainer", "result": "pass", "message": "..."},
        # Add more team checks here as team_check_names grows
    ]
}
```

### store_organisation_checks

Stores organisation-level check results (defined in `terraform/locals.tf` as `organisation_check_names`, e.g., `dependabot_slo`, `secret_scanning_slo`) to individual S3 files. Input format:

```python
{
    "owner": "org-name",
    "run_id": "sfn-execution-id",
    "output_bucket": "bucket-name",
    "check_name": "dependabot_slo",
    "result": "pass",
    "message": "...",
    "details": {...}  # Optional detailed information
}
```

## Extensible Multi-Check Pattern

All check types (repository, team, and organisation) support multiple checks running in parallel per entity, configured via lists in `terraform/locals.tf`:

### Repository Checks

- Configured via `repository_check_names` in `terraform/locals.tf`
- Step Function flow: RepositoryChecksMap (Distributed Map) → RepositoryChecksParallel (runs all checks per repo) → store_repository_output
- S3 output: `audit-runs/<owner>/<run_id>/repositories/<repository-name>.json` with structure `{checks: {check_name: {...}, ...}}`

### Team Checks

- Configured via `team_check_names` in `terraform/locals.tf`
- Step Function flow: TeamChecksMap → TeamChecksParallel (runs all checks) → store_team_checks
- S3 output: `audit-runs/<owner>/<run_id>/teams/<team-slug>.json` with structure `{checks: {check_name: {...}, ...}}`

### Organisation Checks

- Configured via `organisation_check_names` in `terraform/locals.tf`
- Step Function flow: OrganisationChecks (Parallel branches, one per check) → store_organisation_checks (per check)
- Each check stored separately: `audit-runs/<owner>/<run_id>/organisation-checks/<check-name>.json`

**Adding a new check in any category:** Add the check name to the appropriate list in `terraform/locals.tf` and create a handler following the established pattern. The step function automatically includes it via dynamic branching/mapping.

## Writing a New Handler

When adding a new Lambda, use this decision rule:

### Use `@github_handler` when

- the handler needs a GitHub API client
- the handler uses `owner` from the incoming event
- the handler should participate in the standard start/end rate-limit logging

### Do not use `@github_handler` when

- the handler works only on data already provided in the event
- the handler talks to a different external system
- the handler has materially different setup requirements that would make the shared wrapper misleading

For GitHub-backed handlers, keep the body narrow:

- read the event fields needed by the specific check
- call one library function
- add any required output fields such as `check_name`
- trim payload size where needed before returning

## Response Shape Guidance

Most policy check handlers return a compact object like:

```json
{
  "check_name": "codeowners",
  "result": "pass",
  "message": "CODEOWNERS file exists"
}
```

This is important because many of these handlers run inside Step Functions parallel and map states. Responses should stay small and deterministic.

If a library function returns large or verbose fields, trim them in the handler before returning. `team_maintainer` is one example where extra detail is removed to reduce payload size.

## Dependency Layer

All Lambda functions share a single dependency layer (`aws_lambda_layer_version.dependencies`) that packages third-party Python packages separately from handler code. This keeps individual function zips small and avoids duplicating dependencies.

### S3-backed publication

The layer zip (`build/dependency-layer.zip`, ~21 MB) is uploaded to the audit output S3 bucket before `PublishLayerVersion` is called. Terraform manages this as `aws_s3_object.dependency_layer` at the key `layers/dependency-layer.zip`.

The `aws_lambda_layer_version` resource references the S3 object directly:

```hcl
resource "aws_lambda_layer_version" "dependencies" {
  s3_bucket         = aws_s3_bucket.audit_output.id
  s3_key            = aws_s3_object.dependency_layer.key
  s3_object_version = aws_s3_object.dependency_layer.version_id
  ...
}
```

This avoids streaming the zip from the local machine during `PublishLayerVersion`, which would otherwise hit the AWS SigV4 5-minute request signing window on slow or interrupted connections.

### Update behaviour

Because the audit output bucket has versioning enabled, each `terraform apply` that produces a new layer zip:

1. Uploads the new zip to the same S3 key, creating a new S3 object version.
2. The changed `s3_object_version` causes Terraform to publish a new (immutable) Lambda layer version.
3. All `aws_lambda_function.audit` resources are updated to reference the new layer ARN.

If the zip content has not changed (same `etag`), the S3 object and layer version are both no-ops.

## Practical Benefits

This structure gives the project a few concrete advantages:

- less duplicated setup code across GitHub-backed Lambdas
- consistent logging across handlers
- smaller handler modules that are easier to review and test
- a clear boundary between Lambda orchestration and GitHub integration

As the project grows, new shared concerns should usually follow the same rule: put Lambda execution concerns in `utils/lambda_handler.py`, and keep service-specific code in service-specific utilities.
