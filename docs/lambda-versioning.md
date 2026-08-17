# Release Tagging and Traceability

This document describes how release versions are tagged and traced across GitHub and AWS in this deployment.

## Overview

Each deployment is tagged with a release identifier for correlation between GitHub releases and AWS resources. This ensures you can verify which GitHub commit/tag is running in AWS at any time.

## Release Version

The `release_version` Terraform variable is passed from the Concourse CI pipeline and identifies the deployment:

- **Automated deployments:** Set to the GitHub release tag (e.g., `v1.2.3`)
- **Manual deployments:** Defaults to `"manual"`

The release version is:

- Embedded in Lambda function descriptions for traceability
- Added as an AWS resource tag (`ReleaseVersion`) on Lambdas and the Step Functions state machine
- Exposed as a `RELEASE_VERSION` environment variable for functions that need it
- Included in the Step Functions state machine definition comment

### Example

```bash
# Concourse pipeline passes the release tag
release_version="v1.2.3"

# This creates:
# - Lambda descriptions: "GitHub policy audit rate-limit (v1.2.3)"
# - CloudWatch tag: ReleaseVersion = "v1.2.3"
# - Step Functions comment: "Weekly GitHub organisation policy audit (release: v1.2.3)."
```

## Step Functions Invocation

Step Functions invokes Lambda functions directly by their unqualified ARN, which automatically uses the latest deployed code (`$LATEST`):

```text
Function ARN: arn:aws:lambda:eu-west-2:123456789:function:sdp-dev-github-policy-audit-rate-limit
```

When you deploy, the new code is available immediately to all new Step Functions executions.

## Configuration Variables

| Variable          | Default    | Purpose                                                                |
| ----------------- | ---------- | ---------------------------------------------------------------------- |
| `release_version` | `"manual"` | Identifier for the deployed release, used for tagging and traceability |

This variable is passed from Concourse CI during automated deployments or defaults to `"manual"` for manual Terraform runs, helping identify how the deployment was triggered.

## Example Deployment Flow

1. **Concourse CI:** GitHub release tagged `v1.5.0` triggers the pipeline
2. **Build script:** Compiles Lambda functions
3. **Deploy script (`terraform_infra.sh`):** Sets `release_version="v1.5.0"`
4. **Terraform apply:**
   - Each Lambda is updated with new code
   - Lambda descriptions are updated with release tag
   - Step Functions definition comment includes `(release: v1.5.0)`
   - Lambda functions and the Step Functions state machine are tagged with `ReleaseVersion = v1.5.0`
5. **EventBridge rules:** Trigger Step Functions to invoke Lambdas
6. **Execution:** All Lambda invocations use the newly deployed code

## Traceability

To verify which release is running in AWS, simply navigate to the object in the AWS console (Lambda, Step Functions, etc.) and check the description or tags for the `ReleaseVersion`. This allows you to correlate the deployed code with the corresponding GitHub release.
