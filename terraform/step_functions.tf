resource "aws_iam_role" "step_function" {
  name = "${local.lambda_name_prefix}-step-function-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "step_function_invoke_lambda" {
  name = "${local.lambda_name_prefix}-step-function-lambda-invoke"
  role = aws_iam_role.step_function.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
        ]
        Resource = [for lambda in aws_lambda_function.audit : lambda.arn]
      },
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:CreateLogStream",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutLogEvents",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups",
        ]
        # checkov:skip=CKV_AWS_290: All CloudWatch Logs actions for Step Functions require * per AWS documentation
        # checkov:skip=CKV_AWS_355: ^ Same as above
        Resource = "*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "step_function" {
  name              = "/aws/states/${local.lambda_name_prefix}"
  retention_in_days = var.step_function_log_retention_days
}

resource "aws_sfn_state_machine" "github_policy_audit" {
  name     = "${local.lambda_name_prefix}-state-machine"
  role_arn = aws_iam_role.step_function.arn

  definition = jsonencode({
    Comment = "Weekly GitHub organisation policy audit."
    StartAt = "Initialise"
    States = {
      Initialise = {
        Type = "Parallel"
        Branches = [
          {
            StartAt = "list_repositories"
            States = {
              list_repositories = {
                Type     = "Task"
                Resource = aws_lambda_function.audit["list_repositories"].arn
                End      = true
              }
            }
          },
          {
            StartAt = "list_teams"
            States = {
              list_teams = {
                Type     = "Task"
                Resource = aws_lambda_function.audit["list_teams"].arn
                End      = true
              }
            }
          },
        ]
        ResultPath = "$.initial_data"
        Next       = "PrepareInput"
      }
      PrepareInput = {
        Type = "Pass"
        Parameters = {
          "owner.$"        = "$.owner"
          "levels.$"       = "$.levels"
          "repositories.$" = "$.initial_data[0]"
          "teams.$"        = "$.initial_data[1]"
        }
        ResultPath = "$"
        Next       = "OrganisationChecks"
      }
      OrganisationChecks = {
        Type = "Parallel"
        Branches = [
          {
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
          },
          {
            StartAt = "secret_scanning_slo"
            States = {
              secret_scanning_slo = {
                Type     = "Task"
                Resource = aws_lambda_function.audit["secret_scanning_slo"].arn
                Parameters = {
                  "owner.$" = "$.owner"
                }
                End = true
              }
            }
          },
          {
            StartAt = "TeamMaintainerMap"
            States = {
              TeamMaintainerMap = {
                Type           = "Map"
                ItemsPath      = "$.teams"
                MaxConcurrency = var.team_map_max_concurrency
                ItemSelector = {
                  "owner.$" = "$.owner"
                  "team.$"  = "$$.Map.Item.Value"
                }
                ItemProcessor = {
                  ProcessorConfig = {
                    Mode = "INLINE"
                  }
                  StartAt = "team_maintainer"
                  States = {
                    team_maintainer = {
                      Type     = "Task"
                      Resource = aws_lambda_function.audit["team_maintainer"].arn
                      Parameters = {
                        "owner.$"     = "$.owner"
                        "team_slug.$" = "$.team.slug"
                      }
                      End = true
                    }
                  }
                }
                End = true
              }
            }
          },
        ]
        ResultPath = "$.organisation_results"
        Next       = "RepositoryChecksMap"
      }
      RepositoryChecksMap = {
        Type           = "Map"
        ItemsPath      = "$.repositories"
        MaxConcurrency = var.repository_map_max_concurrency
        ItemSelector = {
          "owner.$"      = "$.owner"
          "repository.$" = "$$.Map.Item.Value"
        }
        ItemProcessor = {
          ProcessorConfig = {
            Mode = "INLINE"
          }
          StartAt = "RepositoryChecksParallel"
          States = {
            RepositoryChecksParallel = {
              Type = "Parallel"
              Branches = [
                for check_name in local.repository_check_names : {
                  StartAt = check_name
                  States = {
                    (check_name) = {
                      Type     = "Task"
                      Resource = aws_lambda_function.audit[check_name].arn
                      Parameters = {
                        "owner.$"           = "$.owner"
                        "repository_name.$" = "$.repository.name"
                        "data.$"            = "$.repository.data"
                      }
                      # TODO: Assess best option here when getting within the Step Function limits.
                      # For now, we only carry the check name, result and message forward to the next step, removing the details key.
                      # We will need to assess if details is needed in the future, and if so, we will need to consider alternatives,
                      # such as storing the details in S3 and passing the S3 key forward, or slimming down the details to only include the most important information.
                      ResultSelector = {
                        "check_name.$" = "$.check_name"
                        "result.$"     = "$.result"
                        "message.$"    = "$.message"
                      }
                      End = true
                    }
                  }
                }
              ]
              ResultPath = "$.check_results"
              Next       = "FormatRepositoryChecks"
            }
            FormatRepositoryChecks = {
              Type = "Pass"
              Parameters = {
                "repository_name.$" = "$.repository.name"
                "checks.$"          = "$.check_results"
              }
              End = true
            }
          }
        }
        ResultPath = "$.repository_results"
        Next       = "store_output"
      }
      store_output = {
        Type     = "Task"
        Resource = aws_lambda_function.audit["store_output"].arn
        Parameters = {
          "owner.$"                = "$.owner"
          "teams.$"                = "$.teams"
          "organisation_results.$" = "$.organisation_results"
          "repository_results.$"   = "$.repository_results"
          "team_results.$"         = "$.organisation_results[2]"
        }
        End = true
      }
    }
  })

  tracing_configuration {
    enabled = true
  }

  logging_configuration {
    level                  = "ALL"
    include_execution_data = true
    log_destination        = "${aws_cloudwatch_log_group.step_function.arn}:*"
  }
}
