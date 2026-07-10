# Tests that resource names follow the expected convention for each environment.

mock_provider "aws" {
  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
    }
  }
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/mock-role"
    }
  }
  mock_resource "aws_lambda_layer_version" {
    defaults = {
      arn = "arn:aws:lambda:eu-west-2:123456789012:layer:mock-layer:1"
    }
  }
  mock_resource "aws_sfn_state_machine" {
    defaults = {
      arn = "arn:aws:states:eu-west-2:123456789012:stateMachine:mock-state-machine"
    }
  }
  mock_resource "aws_s3_bucket" {
    defaults = {
      arn = "arn:aws:s3:::mock-bucket"
      id  = "mock-bucket"
    }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = {
      arn = "arn:aws:logs:eu-west-2:123456789012:log-group:mock-log-group"
    }
  }
}

variables {
  github_owner                   = "ONS-Innovation"
  github_app_id_secret_name      = "test-app-id"
  github_private_key_secret_name = "test-private-key"
}

override_data {
  target = data.terraform_remote_state.vpc
  values = {
    outputs = {
      vpc_id          = "vpc-00000000000000000"
      private_subnets = ["subnet-00000000000000001", "subnet-00000000000000002"]
    }
  }
}

run "dev_resource_naming" {
  assert {
    condition     = local.lambda_name_prefix == "sdp-dev-github-policy-audit"
    error_message = "Lambda name prefix should be sdp-dev-github-policy-audit."
  }

  assert {
    condition     = local.audit_output_bucket == "sdp-dev-github-policy-audit"
    error_message = "Audit output bucket name should be sdp-dev-github-policy-audit."
  }

  assert {
    condition     = aws_s3_bucket.audit_output.bucket == "sdp-dev-github-policy-audit"
    error_message = "S3 bucket name should be sdp-dev-github-policy-audit."
  }

  assert {
    condition     = aws_iam_role.lambda_execution.name == "sdp-dev-github-policy-audit-lambda-role"
    error_message = "Lambda IAM role name should be sdp-dev-github-policy-audit-lambda-role."
  }

  assert {
    condition     = aws_iam_role.step_function.name == "sdp-dev-github-policy-audit-step-function-role"
    error_message = "Step Functions IAM role name should be sdp-dev-github-policy-audit-step-function-role."
  }

  assert {
    condition     = aws_iam_role.eventbridge_step_function.name == "sdp-dev-github-policy-audit-eventbridge-role"
    error_message = "EventBridge IAM role name should be sdp-dev-github-policy-audit-eventbridge-role."
  }

  assert {
    condition     = aws_sfn_state_machine.github_policy_audit.name == "sdp-dev-github-policy-audit-state-machine"
    error_message = "State machine name should be sdp-dev-github-policy-audit-state-machine."
  }

  assert {
    condition     = aws_cloudwatch_event_rule.weekly_audit.name == "sdp-dev-github-policy-audit-weekly-trigger"
    error_message = "EventBridge rule name should be sdp-dev-github-policy-audit-weekly-trigger."
  }

  assert {
    condition     = aws_lambda_function.audit["list_repositories"].function_name == "sdp-dev-github-policy-audit-list-repositories"
    error_message = "Lambda function name should replace underscores with hyphens."
  }

  assert {
    condition     = aws_lambda_function.audit["store_output"].function_name == "sdp-dev-github-policy-audit-store-output"
    error_message = "store_output Lambda function name should replace underscores with hyphens."
  }
}

run "prod_resource_naming" {
  variables {
    env_name = "sdp-prod"
  }

  assert {
    condition     = local.lambda_name_prefix == "sdp-prod-github-policy-audit"
    error_message = "Lambda name prefix should be sdp-prod-github-policy-audit for prod."
  }

  assert {
    condition     = aws_s3_bucket.audit_output.bucket == "sdp-prod-github-policy-audit"
    error_message = "S3 bucket name should be sdp-prod-github-policy-audit for prod."
  }

  assert {
    condition     = aws_sfn_state_machine.github_policy_audit.name == "sdp-prod-github-policy-audit-state-machine"
    error_message = "State machine name should be sdp-prod-github-policy-audit-state-machine for prod."
  }
}
