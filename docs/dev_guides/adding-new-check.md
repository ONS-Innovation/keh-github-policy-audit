# Adding a new check

This guide goes through the changes necessary to add a new policy check to the policy audit tool.

## Checklist

Here is a checklist to ensure that you have completed all the relevant tasks to add a new repository/organisation level check.

### Repository checks

- Create handler file `github_policy_audit/functions/repository_checks/<check_name>/handler.py`.
- Implement and register the handler, invoking the policy methods check with event data or necessary API requests.
- Add a handler test in `tests/functions/repository_checks/`.
- Add the Lambda definition and check name to `locals.tf`.
- Update Terraform test counts in `lambda.tftest.hcl` and `state_machine.tftest.hcl`.
- Update `step-function-flow.md` and `README.md`.

### Organisation checks

- Create handler file `github_policy_audit/functions/organisation_checks/<check_name>/handler.py`.
- Implement and register the handler, invoking the corresponding policy methods check.
- Add a handler test in `tests/functions/organisation_checks/<check_name>/`.
- Add the Lambda definition to `locals.tf` and the check to `OrganisationChecks` in `step_function.tf`.
- Pass required event parameters to the state machine task.
- Update Terraform test counts and relevant documentation.

## Adding a handler

To add a check, you will need to add a handler to the directory you are interested in adding a check for.

- Make a new directory inside `github_policy_audit/functions/<check_type>/` named after the check that you wish to add, where `check_type` refers to repository and organisation checks.
- Make a new file inside that directory named `handler.py`, and add the appropriate handler code to the file. Using the handler for codeowners as an example:

```python

@github_handler
def handler(event, context, client):
    """Step Function invokes with {"owner": "...", "repository_name": "..."}."""
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

Refer to the [documentation on lambda structure](../lambda-structure.md) to ensure that the layout of your lambdas remain consistent with the project.

You must import the check that you are implementing from the policy methods library. If the check needs parameters like `owner` or `repository_name`, these can be grabbed from the `event` dictionary.

In the event that the check needs an extra parameter that is not found in the `event` dictionary, you can instead make an API request to the endpoint that will give you that parameter. For instance, the `branch_protection` policy check requires a `branch_name`, which cannot be found in the `event` dictionary, so we use `client.make_request()` to grab the endpoint that holds that parameter. This should only be done sparingly, and developers should use data from the `event` dictionary where possible.

```python
    branches = client.make_request(
        "GET", f"/repos/{event['owner']}/{event['repository_name']}/branches"
    ).json()
```

After the implementation of the handler is done. You will need to add a test for it in `tests/functions/<check_type>/`. In the new file you created, you will need to make a class for that test. For example for `test_inactivity.py`, you would have the class `TestInactivityHandler`.

### Repository Terraform

To update the terraform with the new check and the lambda to the step function, go into `locals.tf` and add an entry for the check in `lambda_definitions`. An example for codeowners is given below:

```python
codeowners = {
    zip_path = "${local.lambda_source_root}/repository_checks-codeowners.zip"
    handler  = "functions.repository_checks.codeowners.handler.handler"
}
```

Further to this, add in the name of the policy check `repository_check_names` array:

```python
  repository_check_names = [
    "codeowners",
    "dependabot",
    "external_pull_request",
    ...
  ]
```

After this, you will need to update the Terraform tests. To do this you will need to update `lambda.tftest.hcl` and `state_machine.tftest.hcl`. In both files, the main task to complete would be to change the number of lambda's being looked at. For instance, in `lambda.tftest.hcl`:

```python
assert {
    condition     = length(output.lambda_function_names) == 20
    error_message = "lambda_function_names output should include all 20 Lambda functions."
  }

```

The above test would remain the same, except we would bump the value `20` to `21` to account for the new lambda we just added into the step function.

### Organisation Terraform

Updating the terraform for organisation-level checks is similar to updating repository-level checks. All that needs to be done is to update the `locals.tf` file and also update the `step_function.tf` file. In the `step_functions.tf` file, what needs to be updated is the `OrganisationChecks` variable. An example is given with `dependabot_slo`:

```python
StartAt = "dependabot_slo"
States = {
    dependabot_slo = {
    Type     = "Task"
    Resource = aws_lambda_function.audit["dependabot_slo"].arn
    Parameters = {
        "owner.$"  = "$.owner"
        "levels.$" = "$.levels"
    }
    End = true
    }
}
```

Thereafter the tests must be updated in the same way as for repository-level checks by updating `lambda.tftest.hcl` and `state_machine.tftest.hcl`. You simply need to update the number of lambdas being looked at.

### Documentation

Once all the technical details have been implemented, the documentation must also be updated. The main documentation to be updated are:

- `step-function-flow.md`
- `README.md`

In `step-function-flow.md`, the `#flow` and `#stage-summary` sections must be updated. The `#flow` sections outlines a diagram of the step function and `#stage-summary` is gives a summary table of all the stages in the step function. For the repository checks, you will simply need to add the check name to the lambdas column.

In `README.md`, the `#check-handlers` section must be updated. Usually this simply means to add in the handler module name into the repository-scoped-checks row. For example `functions.repository_checks.repository_access.handler`.
