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
  github_owner                   = "ONS-Innovation"
  github_app_id_secret_name      = "test-app-id"
  github_private_key_secret_name = "test-private-key"
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
