# GitHub Policy Audit

A tool used to audit GitHub Organisations for compliance with ONS' GitHub Usage Policy. Built using the [KEH Policy Methods Library](https://github.com/ONS-Innovation/keh-policy-methods-library), this tool produces a report of the audit findings, which can be used to identify areas of non-compliance and inform remediation efforts. Additionally, these reports can track compliance over time, providing a historical record of the organisation's adherence to the policy, and its progress towards achieving compliance.

## Table of Contents

- [GitHub Policy Audit](#github-policy-audit)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Makefile](#makefile)
  - [Running the Project](#running-the-project)
    - [1. Setup environment](#1-setup-environment)
    - [2. Set environment variables](#2-set-environment-variables)
    - [3. Run command](#3-run-command)
    - [4. Payload summary](#4-payload-summary)
      - [Repository Listing](#repository-listing)
      - [Organisation Team Listing](#organisation-team-listing)
      - [Rate Limit Checkpoint](#rate-limit-checkpoint)
      - [Check Handlers](#check-handlers)
      - [Output Handlers](#output-handlers)
  - [Deployment](#deployment)
    - [Deployments with Concourse](#deployments-with-concourse)
    - [Manual Deployment](#manual-deployment)
      - [Building the Lambda Functions](#building-the-lambda-functions)
      - [Terraform Deployment](#terraform-deployment)
        - [What Terraform provisions](#what-terraform-provisions)
        - [Terraform file structure](#terraform-file-structure)
        - [Terraform Deployment Steps](#terraform-deployment-steps)
        - [Terraform Variables](#terraform-variables)
  - [Documentation](#documentation)
    - [GitHub Actions for Documentation](#github-actions-for-documentation)
    - [Local Development of Documentation](#local-development-of-documentation)
  - [Linting and Testing](#linting-and-testing)
    - [GitHub Actions](#github-actions)
    - [Running Tests and Linters Locally](#running-tests-and-linters-locally)
      - [Primary Language](#primary-language)
      - [Terraform](#terraform)
      - [MegaLinter](#megalinter)
      - [Documentation linting and building](#documentation-linting-and-building)

## Prerequisites

- Python 3.12 or higher
- Poetry for dependency management
- Node.js and npm for documentation linting (Markdownlint)

## Makefile

This project uses a Makefile to simplify common tasks.
To see the available commands, run:

```bash
make help
```

## Running the Project

### 1. Setup environment

```bash
python -m venv venv
source venv/bin/activate
poetry install
```

### 2. Set environment variables

```bash
export AWS_REGION=eu-west-2
export GITHUB_APP_ID_SECRET_NAME=<your-app-id-secret-name>
export GITHUB_PRIVATE_KEY_SECRET_NAME=<your-private-key-secret-name>
export ENVIRONMENT=local
export LOG_PRETTY_JSON=true
export APP_LOG_FORMAT=TEXT
```

`GITHUB_APP_ID_SECRET_NAME` should point to a secret containing a JSON object with the GitHub App ID under the `AppID` key (for example: `{"AppID":"123456"}`).
`GITHUB_PRIVATE_KEY_SECRET_NAME` should point to a separate secret containing only the GitHub App private key as plain text (PEM), not a key-value JSON object.
`ENVIRONMENT` controls output behaviour for `functions.store_repository_output.handler` and `functions.store_output.handler`:

- `local` (default): writes output JSON to `outputs/<owner>/` and does not call AWS S3.
- `prod`: writes output JSON to S3 and requires `S3_BUCKET_NAME`.

`LOG_PRETTY_JSON` controls the format of structured application log messages:

- false (default): compact single-line JSON log payloads.
- true: pretty-printed multi-line JSON payloads, useful for local debugging.

`APP_LOG_FORMAT` controls how `utils/structured_logging.py` emits records to Python logging:

- `TEXT` (default): emit JSON payload in the log message string (best for local CLI use).
- `JSON`: emit event name as message and fields via logger `extra` for Lambda JSON logs.

In deployed Lambda, Terraform sets `APP_LOG_FORMAT=JSON`.
If `APP_LOG_FORMAT` is unset, the code falls back to the Lambda runtime value `AWS_LAMBDA_LOG_FORMAT` when present.

For production Lambda deployments, keep `LOG_PRETTY_JSON` unset so CloudWatch log volume remains lower.

Detailed logging conventions and examples are documented in `docs/logging-patterns.md`.

`boto3` uses the standard AWS credential provider chain. For local development, this can come from an AWS CLI SSO profile after running `aws sso login`. In Lambda, credentials are provided by the function's IAM execution role.

If running store output in `prod`, set:

```bash
export S3_BUCKET_NAME=<your-output-bucket>
```

### 3. Run command

Use the helper script in `github_policy_audit/run_handler.py`:

```bash
python github_policy_audit/run_handler.py <handler-module> '<event-json>'
```

Example:

```bash
python github_policy_audit/run_handler.py functions.repository_checks.codeowners.handler '{"owner":"ONS-Innovation","repository_name":"keh-github-policy-audit"}'
```

You can also pass a JSON file:

```bash
python github_policy_audit/run_handler.py functions.repository_checks.codeowners.handler payload.json --event-file
```

Ready-to-use payload files are provided in `examples/`:

- `examples/repository_event.json`
- `examples/organisation_event.json`
- `examples/dependabot_slo_event.json`
- `examples/naming_convention_event.json`
- `examples/team_maintainer_event.json`
- `examples/rate_limit_event.json`
- `examples/store_output_event.json`
- `examples/store_repository_output_event.json`

To use these examples, run:

```bash
python github_policy_audit/run_handler.py functions.repository_checks.codeowners.handler examples/<example-file>.json --event-file
```

Some repository-scoped handlers can also accept optional repository metadata under `data` when they are invoked downstream of `functions.list_repositories.handler`. This allows the policy methods library to reuse fields already returned by the repository listing and avoid extra GitHub API calls.

`functions.list_repositories.handler` returns only non-archived repositories.

### 4. Payload summary

#### Repository Listing

| Handler modules                       | Required event payload                                                                                                                                                                                                                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `functions.list_repositories.handler` | `{"owner":"<org>","run_id":"<id>","output_bucket":"<bucket>"}` - writes a bare JSON array of repository summaries to `s3://<bucket>/audit-runs/<owner>/<run_id>/repositories-list.json` and returns an S3 reference. In the step function the `run_id` and `output_bucket` are injected automatically. |

#### Organisation Team Listing

| Handler modules                | Required event payload |
| ------------------------------ | ---------------------- |
| `functions.list_teams.handler` | `{"owner":"<org>"}`    |

#### Rate Limit Checkpoint

| Handler modules                | Required event payload                           |
| ------------------------------ | ------------------------------------------------ | ----------------- |
| `functions.rate_limit.handler` | `{"owner":"<org>","checkpoint":"rate-limit-start | rate-limit-end"}` |

Rate-limit telemetry is collected only by this checkpoint handler at workflow boundaries.

#### Check Handlers

| Checks                                                  | Handler modules                                                                                                                                                                                                                                                                                                                                                                                                    | Required event payload                                                                                        |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Repository-scoped checks                                | `functions.repository_checks.codeowners.handler`, `functions.repository_checks.dependabot.handler`, `functions.repository_checks.external_pull_request.handler`, `functions.repository_checks.gitignore.handler`, `functions.repository_checks.license.handler`, `functions.repository_checks.pirr.handler`, `functions.repository_checks.readme.handler`, `functions.repository_checks.repository_access.handler` | `{"owner":"<org>","repository_name":"<repo>"}`                                                                |
| Repository-scoped checks with optional passthrough data | `functions.repository_checks.inactivity.handler`, `functions.repository_checks.security_scanning.handler`                                                                                                                                                                                                                                                                                                          | `{"owner":"<org>","repository_name":"<repo>"}` or `{"owner":"<org>","repository_name":"<repo>","data":{...}}` |
| Secret scanning SLO                                     | `functions.organisation_checks.secret_scanning_slo.handler`                                                                                                                                                                                                                                                                                                                                                        | `{"owner":"<org>"}`                                                                                           |
| Dependabot SLO                                          | `functions.organisation_checks.dependabot_slo.handler`                                                                                                                                                                                                                                                                                                                                                             | `{"owner":"<org>","levels":["critical","high"]}` (`levels` optional)                                          |
| Naming convention                                       | `functions.repository_checks.naming_convention.handler`                                                                                                                                                                                                                                                                                                                                                            | `{"owner":"<org>","repository_name":"<repo>"}`                                                                |
| Team maintainer                                         | `functions.organisation_checks.team_maintainer.handler`                                                                                                                                                                                                                                                                                                                                                            | `{"owner":"<org>","team_slug":"<team>"}`                                                                      |

#### Output Handlers

| Handler modules                                   | Required event payload                                                                                                                                                                   |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `functions.store_repository_output.handler`       | `{"owner":"<org>","run_id":"<execution-id>","repository_name":"<repo>","checks":[{"check_name":"readme","status":"pass"}]}`                                                              |
| `functions.store_output.handler` (S3 aggregation) | `{"owner":"<org>","run_id":"<execution-id>","output_bucket":"<bucket>","organisation_results":[...],"teams":[...],"team_results":[...],"rate_limit_start":{...},"rate_limit_end":{...}}` |

The scalable production flow stores one repository JSON file at a time under `audit-runs/<owner>/<run_id>/repositories/`, then `store_output` aggregates that prefix and writes the final summary to `audit-results/<owner>/<run_id>.json`.
The final summary and terminal Step Functions output also include `rate-limit-start` and `rate-limit-end` checkpoint objects.

## Deployment

### Deployments with Concourse

<!-- Instructions for deploying the project using Concourse go here. This can be copied from other KEH repositories. -->

### Manual Deployment

#### Building the Lambda Functions

Before deploying the Lambda functions, they must be built and packaged. This can be done using the provided Makefile:

```bash
make build
```

This will create a `build` directory containing the packaged Lambda functions and the dependency layer.

There are two scripts that handle the building process:

- `scripts/build-dependency-layer.sh`: This script installs the required dependencies into a temporary directory and packages them into a zip file for the Lambda layer.
- `scripts/build-lambda-functions.sh`: This script packages each Lambda function into its own zip file, ready for deployment.

A dependency layer is used to reduce the size of the individual Lambda function packages and to share common dependencies across multiple functions. The dependency layer is built first, followed by the individual Lambda functions.

#### Terraform Deployment

##### What Terraform provisions

Terraform in `terraform/` provisions:

- an S3 bucket for audit outputs
- all Lambda functions from `build/lambdas/*.zip`
- a shared Lambda dependency layer from `build/dependency-layer.zip`
- a Step Functions state machine matching `docs/step-function-flow.md`
- an EventBridge weekly schedule (`cron(0 8 ? * MON *)`) that starts execution

##### Terraform file structure

| File                | Purpose                                                               |
| ------------------- | --------------------------------------------------------------------- |
| `providers.tf`      | AWS provider config and default tags.                                 |
| `variables.tf`      | Input variables for environment, runtime, schedule, and secrets.      |
| `data.tf`           | AWS account/partition data sources used in IAM ARNs.                  |
| `locals.tf`         | Shared locals (Lambda package map, naming, repository check list).    |
| `storage.tf`        | S3 bucket resources for audit output storage.                         |
| `lambda.tf`         | Lambda IAM role/policies, dependency layer, and all Lambda functions. |
| `step_functions.tf` | Step Functions IAM role/policy and state machine definition.          |
| `eventbridge.tf`    | EventBridge schedule rule/target and IAM role to start executions.    |
| `outputs.tf`        | Useful deployment outputs (state machine ARN, Lambda names, bucket).  |

##### Terraform Deployment Steps

1. Build the Lambda functions and dependency layer:

   ```bash
   make build
   ```

2. Copy the example tfvars file for your target environment and fill in any secrets:

   ```bash
   cp terraform/env/dev/example_tfvars.txt terraform/env/dev/dev.tfvars
   # edit dev.tfvars with real secret names
   ```

3. Then run the standard Terraform workflow, pointing at the environment backend and vars:

   ```bash
   cd terraform

   # 1. Initialise with the environment-specific remote backend
   terraform init -backend-config=env/dev/backend-dev.tfbackend -reconfigure

   # 2. Refresh state from the remote backend
   terraform refresh -var-file=env/dev/dev.tfvars

   # 3. Preview changes
   terraform plan -var-file=env/dev/dev.tfvars

   # 4. Apply changes
   terraform apply -var-file=env/dev/dev.tfvars
   ```

   Substitute `dev` with `prod` for production deployments.

##### Terraform Variables

| Variable                                | Required | Default                              | Description                                                                                       |
| --------------------------------------- | -------- | ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `env_name`                              | No       | `sdp-dev`                            | Environment name. Controls bucket/resource naming (e.g. `sdp-dev`, `sdp-prod`).                   |
| `region`                                | No       | `eu-west-2`                          | AWS region to deploy into.                                                                        |
| `github_owner`                          | **Yes**  | -                                    | GitHub organisation name audited on each run.                                                     |
| `github_app_id_secret_name`             | **Yes**  | -                                    | Secrets Manager secret name for the GitHub App ID (`{"AppID":"..."}` JSON).                       |
| `github_private_key_secret_name`        | **Yes**  | -                                    | Secrets Manager secret name for the GitHub App private key (PEM, plain text).                     |
| `lambda_runtime`                        | No       | `python3.12`                         | Lambda runtime identifier.                                                                        |
| `lambda_timeout`                        | No       | `120`                                | Default Lambda timeout in seconds. This can be overridden per Lambda function in `locals.tf`.     |
| `lambda_memory_size`                    | No       | `512`                                | Lambda memory in MB.                                                                              |
| `lambda_reserved_concurrent_executions` | No       | `10`                                 | Reserved concurrent executions per Lambda function. Set to `-1` for unreserved (not recommended). |
| `lambda_log_retention_days`             | No       | `90`                                 | CloudWatch log group retention period in days for Lambda functions.                               |
| `step_function_log_retention_days`      | No       | `90`                                 | CloudWatch log group retention period in days for the Step Functions state machine.               |
| `repository_map_max_concurrency`        | No       | `5`                                  | Max parallel repositories processed in the repository checks map state.                           |
| `team_map_max_concurrency`              | No       | `5`                                  | Max parallel teams processed in the team maintainer map state.                                    |
| `dependabot_slo_levels`                 | No       | `["critical","high","medium","low"]` | Dependabot alert severity levels included in the SLO check.                                       |
| `audit_schedule_expression`             | No       | `cron(0 8 ? * MON *)`                | EventBridge schedule expression for the weekly audit trigger.                                     |
| `audit_run_retention_days`              | No       | `30`                                 | Days to retain per-repository run artifacts under `audit-runs/`.                                  |
| `audit_summary_retention_days`          | No       | `365`                                | Days to retain aggregated summary outputs under `audit-results/`.                                 |

## Documentation

This repository uses [MkDocs](https://www.mkdocs.org/) for documentation. The documentation source files are located in the `docs` directory.

### GitHub Actions for Documentation

MkDocs gets deployed to GitHub Pages using GitHub Actions. The workflow for this is located at `.github/workflows/deploy-docs.yml`.
Before deployment, another GitHub Action workflow runs to check that the documentation builds correctly and has no linting or formatting issues.
This workflow is located at `.github/workflows/ci-docs.yml`.

### Local Development of Documentation

To run the documentation locally:

1. Create a Python virtual environment and activate it.

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install the dependencies for MkDocs.

   ```bash
   make docs-install
   ```

3. Run the MkDocs development server.

   ```bash
   make docs-serve
   ```

## Linting and Testing

### GitHub Actions

This repository has GitHub Actions workflows set up for linting and testing. The workflows are located at:

- `.github/workflows/ci-fmt.yml` for linting and formatting checks (primary language).
- `.github/workflows/ci-terraform.yml` for linting and testing the Terraform configuration.
- `.github/workflows/ci-test.yml` for running automated tests.
- `.github/workflows/ci-docs.yml` for checking that the documentation builds correctly and has no linting or formatting issues.
- `.github/workflows/megalinter.yml` for running MegaLinter, which checks for linting and formatting issues across multiple languages and file types (this is a catch-all linter).
- `.github/workflows/deploy-docs.yml` for deploying documentation to GitHub Pages.

### Running Tests and Linters Locally

#### Primary Language

To run the linters and formatters for the primary language (Python) locally, you can use the following command:

```bash
make lint
```

To apply automatic fixes for any linting or formatting issues found, you can use:

```bash
make fmt
```

To run the tests locally, you can use:

```bash
make test
```

#### Terraform

Terraform tests use the native [`terraform test`](https://developer.hashicorp.com/terraform/language/tests) framework with mock providers - no AWS credentials are required.

Tests live in `terraform/tests/` and are grouped by concern:

| File                       | What it covers                                                                                                                      |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `naming.tftest.hcl`        | Resource names follow the `${env_name}-github-policy-audit-*` convention for dev and prod.                                          |
| `lambda.tftest.hcl`        | All 18 Lambdas are defined, runtime/timeout/memory defaults, environment variables, handler paths, and the shared dependency layer. |
| `storage.tftest.hcl`       | S3 bucket naming, public access block settings, and lifecycle rules for run artifacts and summaries.                                |
| `state_machine.tftest.hcl` | Required states are present, repository map distribution/concurrency, logging config, and EventBridge schedule/input payload.       |

To run the Terraform tests locally:

```bash
make tf-test
```

This will build the Lambda artefacts first (`make build`), then run `terraform test` against all test files.

#### MegaLinter

This repository uses MegaLinter for comprehensive linting across multiple languages and file types.
We use this so that all additional assets in the repository (e.g. YAML files, Markdown files, etc.) are also linted and checked for formatting issues, without having to set up specific linters for each file type.

To run MegaLinter locally, you can use the following command:

```bash
make megalinter
```

#### Documentation linting and building

This repository uses Markdownlint for linting the documentation. To run Markdownlint locally, you can use the following:

```bash
make docs-lint
```

**Note:** This will install `markdownlint-cli` globally via npm if it is not already installed.

To apply automatic fixes for any linting issues found by Markdownlint, you can use:

```bash
make docs-fix
```

To test that the documentation builds correctly, you can use the following command:

```bash
make docs-build
```

**Note:** This depends on MkDocs being set up for the repository. Instructions for setting up MkDocs can be found in the [Documentation](#documentation) section of this README.
