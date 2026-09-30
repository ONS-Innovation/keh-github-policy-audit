# Repository Scorecards

Repository scorecards provide a simple Platinum, Gold, Silver, Bronze, or non-compliant status for each repository in an audit run. The score is derived from the repository check results that are already collected by the workflow.

## Purpose

The scorecard is intended to provide a compact summary of repository policy compliance that can be used in downstream reporting.

A repository rating is based on:

- percentage compliance across repository checks
- required checks for each rating level

A repository only receives a rating if it meets both conditions for that level. Any repositories that do not meet the minimum requirements for any rating are marked as `non-compliant`.

Providing a Platinum, Gold, Silver, or Bronze rating allows for a simple summary of repository compliance without requiring the reader to understand the underlying checks.
It can also help teams prioritise remediation work by focusing on the repositories with a lower rating.

## Rating Rules

The scorecard criteria are defined in [config/scorecard_criteria.json](../config/scorecard_criteria.json).

The file contains one object per rating. Each rating defines:

- `min_compliance`: the minimum percentage of passing repository checks required
- `required_checks`: checks that must pass for the repository to receive that rating

Example:

```json
{
  "<rating_name>": {
    "min_compliance": 90,
    "required_checks": [
      "<check_name>"
    ]
  }
}
```

Any number of ratings can be defined. Ratings are evaluated from highest `min_compliance` to lowest.

## How Ratings Are Calculated

The scorecard logic is applied during final output aggregation in `functions.store_output.handler`.

The process is:

1. Load scorecard criteria.
2. Iterate through repositories in the run.
3. Calculate the highest rating each repository satisfies.
4. Add that rating to the repository record.
5. Count the number of repositories in each rating.

Compliance percentage is calculated from repository-scoped checks only. The derived `is_compliant` field is not included in the percentage calculation.

## Output Shape

The final output includes:

- `summary.repository_ratings`: a count of repositories per rating
- `repositories.<repository_name>.rating`: the repository rating
- `repositories.<repository_name>.checks`: check outputs keyed by check name
- `scorecard_criteria`: the criteria object used to calculate the ratings

Example output excerpt:

```json
{
  "repositories": {
    "repo-a": {
      "checks": {
        "codeowners": {
          "result": "pass"
        },
        "readme": {
          "result": "fail"
        }
      },
      "is_compliant": false,
      "rating": "non-compliant"
    },
    "repo-b": {
      "checks": {
        "codeowners": {
          "result": "pass"
        },
        "readme": {
          "result": "pass"
        },
        "license": {
          "result": "pass"
        }
      },
      "is_compliant": true,
      "rating": "gold"
    }
  },
  "scorecard_criteria": {
    "platinum": {
      "min_compliance": 100,
      "required_checks": []
    },
    "gold": {
      "min_compliance": 90,
      "required_checks": [
        "codeowners",
        "dependabot",
        "security_scanning",
        "readme",
        "pirr",
        "license",
        "repository_access"
      ]
    },
    "silver": {
      "min_compliance": 70,
      "required_checks": [
        "codeowners",
        "dependabot",
        "security_scanning",
        "readme",
        "pirr",
        "license"
      ]
    },
    "bronze": {
      "min_compliance": 50,
      "required_checks": [
        "codeowners",
        "dependabot",
        "security_scanning"
      ]
    }
  },
  "summary": {
    "repository_ratings": {
      "platinum": 0,
      "gold": 1,
      "silver": 0,
      "bronze": 0,
      "non-compliant": 1
    }
  }
}
```

Note: check objects may include additional fields such as `message` or `details`, depending on the originating check handler.

### Why is the scorecard criteria stored in the output?

The scorecard criteria are stored in the output to ensure that the criteria used to calculate the ratings are preserved alongside the results. This allows for:

- transparency in how ratings were derived
- reproducibility of results if the criteria change in future runs
- allows tooling to digest criteria and ratings without needing to load the criteria from S3 or local config

## Configuration Sources

The scorecard criteria are loaded from different locations depending on the environment:

- `local`: `config/scorecard_criteria.json`
- `prod`: `s3://<S3_BUCKET_NAME>/config/scorecard_criteria.json`

This allows the deployed criteria to be updated in S3 without changing Lambda code.

## Terraform Behaviour

Terraform creates the initial S3 scorecard criteria object.

After creation, Terraform ignores content drift for that object. This means:

- the initial config is seeded automatically
- later edits in S3 are not overwritten on the next Terraform apply
- deleting the S3 object will cause Terraform to recreate it
