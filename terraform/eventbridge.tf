resource "aws_iam_role" "eventbridge_step_function" {
  name = "${local.lambda_name_prefix}-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_start_execution" {
  name = "${local.lambda_name_prefix}-eventbridge-start-execution"
  role = aws_iam_role.eventbridge_step_function.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution",
        ]
        Resource = aws_sfn_state_machine.github_policy_audit.arn
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "weekly_audit" {
  name                = "${local.lambda_name_prefix}-weekly-trigger"
  description         = "Weekly trigger for GitHub policy audit state machine."
  schedule_expression = var.audit_schedule_expression
}

resource "aws_cloudwatch_event_target" "weekly_audit_state_machine" {
  rule     = aws_cloudwatch_event_rule.weekly_audit.name
  arn      = aws_sfn_state_machine.github_policy_audit.arn
  role_arn = aws_iam_role.eventbridge_step_function.arn

  input = jsonencode({
    owner  = var.github_owner
    levels = var.dependabot_slo_levels
  })
}
