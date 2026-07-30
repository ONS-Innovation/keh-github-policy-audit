# Tests for Lambda function configuration: count, runtime, timeouts, env vars, and handlers.

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
  organisation_schedules = [
    {
      owner               = "ONS-Innovation"
      schedule_expression = "cron(0 6 ? * MON *)"
    },
  ]
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

run "lambda_definitions_complete" {
  assert {
    condition     = length(local.lambda_definitions) == 19
    error_message = "Expected 19 Lambda function definitions."
  }

  assert {
    condition     = length(aws_lambda_function.audit) == 19
    error_message = "Expected 19 Lambda functions to be provisioned."
  }

  assert {
    condition     = length(local.repository_check_names) == 11
    error_message = "Expected 11 repository check names."
  }

  assert {
    condition = alltrue([
      contains(local.repository_check_names, "codeowners"),
      contains(local.repository_check_names, "dependabot"),
      contains(local.repository_check_names, "external_pull_request"),
      contains(local.repository_check_names, "gitignore"),
      contains(local.repository_check_names, "inactivity"),
      contains(local.repository_check_names, "license"),
      contains(local.repository_check_names, "naming_convention"),
      contains(local.repository_check_names, "pirr"),
      contains(local.repository_check_names, "readme"),
      contains(local.repository_check_names, "repository_access"),
      contains(local.repository_check_names, "security_scanning"),
    ])
    error_message = "repository_check_names is missing one or more expected checks."
  }
}

run "lambda_runtime_config" {
  assert {
    condition     = aws_lambda_function.audit["list_repositories"].runtime == "python3.12"
    error_message = "Lambda runtime should be python3.12."
  }

  assert {
    condition     = aws_lambda_function.audit["list_repositories"].timeout == 600
    error_message = "Lambda list_repositories timeout should be overridden to 600 seconds."
  }

  assert {
    condition     = aws_lambda_function.audit["list_repositories"].memory_size == 512
    error_message = "Lambda memory should default to 512 MB."
  }

  assert {
    condition     = length(aws_lambda_function.audit["list_repositories"].layers) == 1
    error_message = "Lambda should have exactly one layer (the shared dependency layer)."
  }
}

run "lambda_env_vars" {
  assert {
    condition     = aws_lambda_function.audit["store_output"].environment[0].variables["ENVIRONMENT"] == "prod"
    error_message = "Lambda ENVIRONMENT variable should be prod."
  }

  assert {
    condition     = aws_lambda_function.audit["store_output"].environment[0].variables["S3_BUCKET_NAME"] == "sdp-dev-github-policy-audit"
    error_message = "Lambda S3_BUCKET_NAME should match the audit output bucket."
  }

  assert {
    # checkov:skip=CKV_SECRET_6:False positive: This is a test for the correct secret name, not the secret value.
    condition     = aws_lambda_function.audit["store_output"].environment[0].variables["GITHUB_APP_ID_SECRET_NAME"] == "test-app-id"
    error_message = "Lambda GITHUB_APP_ID_SECRET_NAME should match the variable."
  }

  assert {
    # checkov:skip=CKV_SECRET_6:False positive: This is a test for the correct secret name, not the secret value.
    condition     = aws_lambda_function.audit["store_output"].environment[0].variables["GITHUB_PRIVATE_KEY_SECRET_NAME"] == "test-private-key"
    error_message = "Lambda GITHUB_PRIVATE_KEY_SECRET_NAME should match the variable."
  }

  assert {
    condition     = aws_lambda_function.audit["store_output"].environment[0].variables["GITHUB_CLIENT_CACHE_TTL_SECONDS"] == "300"
    error_message = "Lambda GITHUB_CLIENT_CACHE_TTL_SECONDS should default to 300 seconds."
  }
}

run "lambda_handlers" {
  assert {
    condition     = aws_lambda_function.audit["list_repositories"].handler == "functions.list_repositories.handler.handler"
    error_message = "list_repositories handler path is incorrect."
  }

  assert {
    condition     = aws_lambda_function.audit["list_teams"].handler == "functions.list_teams.handler.handler"
    error_message = "list_teams handler path is incorrect."
  }

  assert {
    condition     = aws_lambda_function.audit["rate_limit"].handler == "functions.rate_limit.handler.handler"
    error_message = "rate_limit handler path is incorrect."
  }

  assert {
    condition     = aws_lambda_function.audit["dependabot_slo"].handler == "functions.organisation_checks.dependabot_slo.handler.handler"
    error_message = "dependabot_slo handler path is incorrect."
  }

  assert {
    condition     = aws_lambda_function.audit["store_output"].handler == "functions.store_output.handler.handler"
    error_message = "store_output handler path is incorrect."
  }

  assert {
    condition     = aws_lambda_function.audit["store_repository_output"].handler == "functions.store_repository_output.handler.handler"
    error_message = "store_repository_output handler path is incorrect."
  }
}

run "lambda_layer_name" {
  assert {
    condition     = aws_lambda_layer_version.dependencies.layer_name == "sdp-dev-github-policy-audit-dependencies"
    error_message = "Dependency layer name should be sdp-dev-github-policy-audit-dependencies."
  }

  assert {
    condition     = contains(aws_lambda_layer_version.dependencies.compatible_runtimes, "python3.12")
    error_message = "Dependency layer should be compatible with python3.12."
  }
}

run "lambda_network_and_observability" {
  assert {
    condition = anytrue([
      for rule in aws_security_group.lambda_sg.ingress :
      rule.from_port == 443 &&
      rule.to_port == 443 &&
      rule.protocol == "tcp" &&
      contains(rule.cidr_blocks, "10.0.0.0/16")
    ])
    error_message = "Lambda security group should allow HTTPS ingress from the expected VPC CIDR."
  }

  assert {
    condition = anytrue([
      for rule in aws_security_group.lambda_sg.egress :
      rule.protocol == "-1" &&
      contains(rule.cidr_blocks, "0.0.0.0/0")
    ])
    error_message = "Lambda security group should allow outbound traffic."
  }

  assert {
    condition     = length(aws_lambda_function.audit["list_repositories"].vpc_config[0].subnet_ids) == 2
    error_message = "list_repositories Lambda should be configured with two private subnets."
  }

  assert {
    condition     = length(aws_lambda_function.audit["list_repositories"].vpc_config[0].security_group_ids) == 1
    error_message = "list_repositories Lambda should be configured with exactly one security group."
  }

  assert {
    condition     = aws_lambda_function.audit["list_repositories"].tracing_config[0].mode == "Active"
    error_message = "Lambda tracing should be enabled (Active)."
  }

  assert {
    condition     = aws_lambda_function.audit["list_repositories"].logging_config[0].log_format == "JSON"
    error_message = "Lambda log format should be JSON."
  }

  assert {
    condition     = aws_lambda_function.audit["list_repositories"].reserved_concurrent_executions == 10
    error_message = "Lambda reserved concurrency should default to 10."
  }

  assert {
    condition     = aws_cloudwatch_log_group.audit["list_repositories"].retention_in_days == 90
    error_message = "Lambda log retention should default to 90 days."
  }
}

run "lambda_iam_policies" {
  assert {
    condition     = aws_iam_role_policy_attachment.lambda_basic_execution.policy_arn == "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    error_message = "Lambda role should attach AWSLambdaBasicExecutionRole."
  }

  assert {
    condition     = aws_iam_role_policy_attachment.lambda_vpc_access_execution.policy_arn == "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
    error_message = "Lambda role should attach AWSLambdaVPCAccessExecutionRole."
  }

  assert {
    condition = alltrue([
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "\"AllowGitHubSecretsRead\""),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "\"secretsmanager:GetSecretValue\""),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "\"AllowStoreOutputWrite\""),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "\"s3:PutObject\""),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "\"s3:GetObject\""),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "\"AllowStoreOutputList\""),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "\"s3:ListBucket\""),
    ])
    error_message = "Lambda inline policy should include required Secrets Manager and S3 actions."
  }

  assert {
    condition = alltrue([
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "arn:aws:secretsmanager:eu-west-2:123456789012:secret:test-app-id*"),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "arn:aws:secretsmanager:eu-west-2:123456789012:secret:test-private-key*"),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "arn:aws:s3:::mock-bucket/*"),
      strcontains(aws_iam_role_policy.lambda_permissions.policy, "arn:aws:s3:::mock-bucket"),
    ])
    error_message = "Lambda inline policy should scope resources to expected secrets and audit bucket paths."
  }
}
