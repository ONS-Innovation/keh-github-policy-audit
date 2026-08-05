# Tests for S3 bucket configuration and public access settings.

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

run "bucket_name" {
  assert {
    condition     = aws_s3_bucket.audit_output.bucket == "sdp-dev-github-policy-audit"
    error_message = "Audit output bucket name should be sdp-dev-github-policy-audit."
  }
}

run "public_access_block_enabled" {
  assert {
    condition     = aws_s3_bucket_public_access_block.audit_output.block_public_acls == true
    error_message = "block_public_acls should be true."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.audit_output.block_public_policy == true
    error_message = "block_public_policy should be true."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.audit_output.ignore_public_acls == true
    error_message = "ignore_public_acls should be true."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.audit_output.restrict_public_buckets == true
    error_message = "restrict_public_buckets should be true."
  }
}

run "lifecycle_rules_configured" {
  assert {
    condition     = length(aws_s3_bucket_lifecycle_configuration.audit_output.rule) == 3
    error_message = "Expected three lifecycle rules on audit output bucket (including global abort rule)."
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.audit_output.rule[0].id == "expire-audit-runs"
    error_message = "First lifecycle rule should be expire-audit-runs."
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.audit_output.rule[0].filter[0].prefix == "audit-runs/"
    error_message = "First lifecycle rule should target audit-runs/."
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.audit_output.rule[0].expiration[0].days == 30
    error_message = "audit-runs/ lifecycle rule should default to 30 days."
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.audit_output.rule[1].id == "expire-audit-summaries"
    error_message = "Second lifecycle rule should be expire-audit-summaries."
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.audit_output.rule[1].filter[0].prefix == "audit-results/"
    error_message = "Second lifecycle rule should target audit-results/."
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.audit_output.rule[1].expiration[0].days == 365
    error_message = "audit-results/ lifecycle rule should default to 365 days."
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.audit_output.rule[2].id == "abort-incomplete-multipart-uploads"
    error_message = "Third lifecycle rule should be the global abort rule."
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.audit_output.rule[2].abort_incomplete_multipart_upload[0].days_after_initiation == 1
    error_message = "Global abort rule should set days_after_initiation to 1."
  }
}

run "bucket_versioning_enabled" {
  assert {
    condition     = aws_s3_bucket_versioning.audit_output.versioning_configuration[0].status == "Enabled"
    error_message = "Audit output bucket versioning should be enabled."
  }
}

run "scorecard_criteria_object_seeded" {
  assert {
    condition     = local.scorecard_config_s3_key == "config/scorecard_criteria.json"
    error_message = "Scorecard criteria S3 key should be config/scorecard_criteria.json."
  }

  assert {
    condition     = aws_s3_object.scorecard_criteria.bucket == aws_s3_bucket.audit_output.id
    error_message = "Scorecard criteria object should be stored in the audit output bucket."
  }

  assert {
    condition     = aws_s3_object.scorecard_criteria.key == "config/scorecard_criteria.json"
    error_message = "Scorecard criteria object key is incorrect."
  }

  assert {
    condition     = aws_s3_object.scorecard_criteria.content_type == "application/json"
    error_message = "Scorecard criteria object should have application/json content type."
  }
}
