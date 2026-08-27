# Tests for the Step Functions state machine definition and EventBridge schedule.

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
    {
      owner               = "ONSdigital"
      schedule_expression = "cron(0 8 ? * MON *)"
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

run "state_machine_states" {
  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).StartAt == "PrepareInitialInput"
    error_message = "State machine must start at the Initialise state."
  }

  assert {
    condition = alltrue([
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "RateLimitStart"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "Initialise"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "PrepareInput"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "OrganisationChecks"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "RepositoryChecksMap"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "RateLimitEnd"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "store_output"),
    ])
    error_message = "State machine is missing one or more required states."
  }
}

run "state_machine_concurrency" {
  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.RepositoryChecksMap.MaxConcurrency == 5
    error_message = "RepositoryChecksMap MaxConcurrency should default to 5."
  }

  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.RepositoryChecksMap.ItemProcessor.ProcessorConfig.Mode == "DISTRIBUTED"
    error_message = "RepositoryChecksMap should run in DISTRIBUTED mode for scalability."
  }

  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.OrganisationChecks.Branches[2].States.TeamMaintainerMap.MaxConcurrency == 5
    error_message = "TeamMaintainerMap MaxConcurrency should default to 5."
  }

  assert {
    condition     = length(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.RepositoryChecksMap.ItemProcessor.States.RepositoryChecksParallel.Branches[0].States.codeowners.Retry) == 2
    error_message = "Repository check tasks should define two retry tiers (fast infra, slow rate-limit)."
  }

  assert {
    condition     = contains(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.RepositoryChecksMap.ItemProcessor.States.RepositoryChecksParallel.Branches[0].States.codeowners.Retry[1].ErrorEquals, "States.TaskFailed")
    error_message = "Repository check slow retry tier should include States.TaskFailed."
  }

  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.RepositoryChecksMap.ItemProcessor.States.RepositoryChecksParallel.Branches[0].States.codeowners.Retry[1].IntervalSeconds == 60
    error_message = "Repository check slow retry tier should start at 60 seconds."
  }

  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.RepositoryChecksMap.ItemProcessor.States.RepositoryChecksParallel.Branches[0].States.codeowners.Retry[1].JitterStrategy == "FULL"
    error_message = "Repository check slow retry tier should use FULL jitter strategy."
  }
}

run "state_machine_logging" {
  assert {
    condition     = aws_sfn_state_machine.github_policy_audit.logging_configuration[0].include_execution_data == true
    error_message = "Step Function should enable execution payload logging."
  }
}

run "state_machine_concurrency_overridden" {
  variables {
    repository_map_max_concurrency = 10
    team_map_max_concurrency       = 3
  }

  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.RepositoryChecksMap.MaxConcurrency == 10
    error_message = "RepositoryChecksMap MaxConcurrency should reflect the overridden value."
  }

  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States.OrganisationChecks.Branches[2].States.TeamMaintainerMap.MaxConcurrency == 3
    error_message = "TeamMaintainerMap MaxConcurrency should reflect the overridden value."
  }
}

run "eventbridge_schedule" {
  assert {
    condition     = aws_cloudwatch_event_rule.weekly_audit["ONS-Innovation"].schedule_expression == "cron(0 6 ? * MON *)"
    error_message = "EventBridge schedule for ONS-Innovation should be cron(0 6 ? * MON *)."
  }

  assert {
    condition     = aws_cloudwatch_event_rule.weekly_audit["ONSdigital"].schedule_expression == "cron(0 8 ? * MON *)"
    error_message = "EventBridge schedule for ONSdigital should be cron(0 8 ? * MON *)."
  }
}

run "eventbridge_schedule_overridden" {
  variables {
    organisation_schedules = [
      {
        owner               = "ONS-Innovation"
        schedule_expression = "cron(0 6 ? * WED *)"
      },
    ]
  }

  assert {
    condition     = aws_cloudwatch_event_rule.weekly_audit["ONS-Innovation"].schedule_expression == "cron(0 6 ? * WED *)"
    error_message = "EventBridge schedule should reflect the overridden value."
  }
}

run "eventbridge_input_payload" {
  assert {
    condition     = jsondecode(aws_cloudwatch_event_target.weekly_audit_state_machine["ONS-Innovation"].input).owner == "ONS-Innovation"
    error_message = "EventBridge input payload for ONS-Innovation must include the correct owner."
  }

  assert {
    condition     = jsondecode(aws_cloudwatch_event_target.weekly_audit_state_machine["ONSdigital"].input).owner == "ONSdigital"
    error_message = "EventBridge input payload for ONSdigital must include the correct owner."
  }

  assert {
    condition     = toset(jsondecode(aws_cloudwatch_event_target.weekly_audit_state_machine["ONS-Innovation"].input).levels) == toset(["critical", "high", "medium", "low"])
    error_message = "EventBridge input payload must include all default dependabot severity levels."
  }
}

run "step_function_and_eventbridge_iam" {
  assert {
    condition = alltrue([
      strcontains(aws_iam_role_policy.step_function_invoke_lambda.policy, "\"AllowReadRepositoryList\""),
      strcontains(aws_iam_role_policy.step_function_invoke_lambda.policy, "\"s3:GetObject\""),
    ])
    error_message = "Step Function policy should allow reading repository list object from S3."
  }

  assert {
    condition = alltrue([
      strcontains(aws_iam_role_policy.step_function_invoke_lambda.policy, "\"AllowDistributedMapChildExecutions\""),
      strcontains(aws_iam_role_policy.step_function_invoke_lambda.policy, "\"states:StartExecution\""),
      strcontains(aws_iam_role_policy.step_function_invoke_lambda.policy, "\"states:DescribeExecution\""),
    ])
    error_message = "Step Function policy should allow distributed-map child execution actions."
  }

  assert {
    condition = alltrue([
      strcontains(aws_iam_role_policy.step_function_invoke_lambda.policy, "\"AllowCloudWatchLogs\""),
      strcontains(aws_iam_role_policy.step_function_invoke_lambda.policy, "\"logs:CreateLogDelivery\""),
      strcontains(aws_iam_role_policy.step_function_invoke_lambda.policy, "\"logs:PutLogEvents\""),
    ])
    error_message = "Step Function policy should include required CloudWatch Logs permissions."
  }

  assert {
    condition     = contains(flatten([for statement in jsondecode(aws_iam_role_policy.eventbridge_start_execution.policy).Statement : statement.Action]), "states:StartExecution")
    error_message = "EventBridge policy should allow starting the state machine execution."
  }

  assert {
    condition     = contains(flatten([for statement in jsondecode(aws_iam_role_policy.eventbridge_start_execution.policy).Statement : [statement.Resource]]), aws_sfn_state_machine.github_policy_audit.arn)
    error_message = "EventBridge policy should scope StartExecution to the audit state machine ARN."
  }
}

run "terraform_outputs" {
  assert {
    condition     = output.step_function_arn == aws_sfn_state_machine.github_policy_audit.arn
    error_message = "step_function_arn output should match the state machine ARN."
  }

  assert {
    condition     = length(output.lambda_function_names) == 22
    error_message = "lambda_function_names output should include all 22 Lambda functions."
  }

  assert {
    condition     = output.audit_output_bucket_name == "sdp-dev-github-policy-audit"
    error_message = "audit_output_bucket_name output should match the expected dev bucket name."
  }
}
