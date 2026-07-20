output "step_function_arn" {
  description = "ARN of the GitHub policy audit state machine."
  value       = aws_sfn_state_machine.github_policy_audit.arn
}

output "lambda_function_names" {
  description = "Deployed Lambda function names."
  value       = [for lambda in aws_lambda_function.audit : lambda.function_name]
}

output "audit_output_bucket_name" {
  description = "S3 bucket name where audit output is written."
  value       = aws_s3_bucket.audit_output.bucket
}
