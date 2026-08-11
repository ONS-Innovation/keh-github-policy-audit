# GitHub Policy Audit

The GitHub Policy Audit is a tool used to audit GitHub Organisations for compliance with ONS' GitHub Usage Policy. Built using the [KEH Policy Methods Library](https://github.com/ONS-Innovation/keh-policy-methods-library), this tool produces a report of the audit findings, which can be used to identify areas of non-compliance and inform remediation efforts. Additionally, these reports can track compliance over time, providing a historical record of the organisation's adherence to the policy, and its progress towards achieving compliance.

This repository collects the data for these reports using an AWS Step Function workflow, and stores the results in S3. The reporting half of the project is implemented within the [Digital Landscape](https://github.com/ONSdigital/keh-digital-landscape).

## Getting Started

For detailed documentation on how to run, deploy, and contribute to the GitHub Policy Audit, please refer to the project's `README` at the root of the repository.

The README covers prerequisites, environment setup, how to run the Step Function locally, and deployment instructions.
This documentation (`/docs`) provides more detailed information on the project, including an overview of the tech stack, details on implementation choices, and more.

## Aims of the GitHub Policy Audit

The GitHub Policy Audit aims to:

- Provide an automated mechanism for auditing GitHub Organisations against ONS' GitHub Usage Policy, reducing the manual effort required to identify non-compliance.
- Track compliance over time by storing audit results in S3, enabling historical comparisons and progress reporting.
- Surface actionable findings via repository scorecards, allowing teams to understand and address specific areas of non-compliance.
- Integrate with the [Digital Landscape](https://github.com/ONSdigital/keh-digital-landscape) to provide a centralised reporting view across the organisation.

## Tech Stack

- **Python (`3.12+`)**: The primary programming language used for the Lambda functions and shared utilities.
- **Poetry**: Used for dependency management and packaging.
- **AWS Lambda**: Each check and data-collection step is implemented as an individual Lambda function.
- **AWS Step Functions**: Orchestrates the Lambda functions into a structured audit workflow.
- **AWS S3**: Used to store audit results and scorecard criteria configuration.
- **Terraform**: Used to provision all AWS infrastructure, including Lambdas, Step Functions, S3, and EventBridge.
- **MkDocs**: Used for building this documentation site.
- **GitHub Actions**: Used for CI/CD, including running tests, linting, and deploying documentation to GitHub Pages.
- **Markdownlint**: Used for linting Markdown files in the documentation.
- **MegaLinter**: Used as a catch-all linter across the codebase.
- **Ruff + MyPy**: Used for linting and type checking the Python codebase.

## Documentation Structure

```bash
docs/
├── index.md                        # This file.
├── documentation.md                # How the project documentation is structured.
├── repository-scorecards.md        # How repositories are scored for compliance.
├── logging-patterns.md             # Structured logging conventions used across the project.
├── lambda-structure.md             # How Lambda functions are organised and structured.
├── step-function-flow.md           # The AWS Step Function workflow that orchestrates the audit.
└── rate-limit-considerations.md    # How the tool handles GitHub API rate limits.
```
