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

run "state_machine_states" {
  assert {
    condition     = jsondecode(aws_sfn_state_machine.github_policy_audit.definition).StartAt == "Initialise"
    error_message = "State machine must start at the Initialise state."
  }

  assert {
    condition = alltrue([
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "Initialise"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "PrepareInput"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "OrganisationChecks"),
      contains(keys(jsondecode(aws_sfn_state_machine.github_policy_audit.definition).States), "RepositoryChecksMap"),
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
    condition     = aws_cloudwatch_event_rule.weekly_audit.schedule_expression == "cron(0 8 ? * MON *)"
    error_message = "EventBridge schedule should default to cron(0 8 ? * MON *)."
  }
}

run "eventbridge_schedule_overridden" {
  variables {
    audit_schedule_expression = "cron(0 6 ? * WED *)"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.weekly_audit.schedule_expression == "cron(0 6 ? * WED *)"
    error_message = "EventBridge schedule should reflect the overridden value."
  }
}

run "eventbridge_input_payload" {
  assert {
    condition     = jsondecode(aws_cloudwatch_event_target.weekly_audit_state_machine.input).owner == "ONS-Innovation"
    error_message = "EventBridge input payload must include the github_owner."
  }

  assert {
    condition     = toset(jsondecode(aws_cloudwatch_event_target.weekly_audit_state_machine.input).levels) == toset(["critical", "high", "medium", "low"])
    error_message = "EventBridge input payload must include all default dependabot severity levels."
  }
}
