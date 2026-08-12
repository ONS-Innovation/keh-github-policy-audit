# Lambda Structure

This project uses a consistent Lambda layout so that each function stays small and focused:

- the handler module is responsible for the Lambda entry point, any processing and its response
- shared setup lives in utilities
- business logic lives in `policy_methods_library`

This keeps individual handlers easy to scan and reduces duplication across the audit workflow.

## Layout

All Lambda functions live in the `/functions` folder, with a subfolder for each function. Functions are organised by their type, for example any general functions (i.e. not specific to a single check) live in the `functions/` folder itself, while check-specific functions live in `functions/repository_checks/` or `functions/organisation_checks/`. This help segregate the different types of lambdas based on their purpose and usage.

To give some examples:

- `functions/list_repositories/handler.py` is a general function that lists all repositories for an organisation.
- `functions/repository_checks/codeowners/handler.py` is a repository check function that checks for the presence of a CODEOWNERS file in a repository.
- `functions/organisation_checks/team_maintainer/handler.py` is an organisation check function that checks if a team has a maintainer.

When organising a new function consider the following questions:

1. Does the function operate on a single repository or organisation? If so, it should live in the appropriate `repository_checks` or `organisation_checks` folder.
2. Does the function operate on multiple repositories or organisations? (i.e. it aggregates data across them) If so, it should live in the `functions/` folder itself.

Additional directories can be added to the `functions/` folder if needed, but should be kept to a minimum to avoid unnecessary complexity.

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


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@github_handler
def handler(event, context, client):
    result = check_codeowners(client, event["repository_name"])
    result["check_name"] = "codeowners"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
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
