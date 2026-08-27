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
        Sid    = "AllowReadRepositoryList"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
        ]
        Resource = "${aws_s3_bucket.audit_output.arn}/audit-runs/*/repositories-list.json"
      },
      {
        Sid    = "AllowDistributedMapChildExecutions"
        Effect = "Allow"
        Action = [
          "states:StartExecution",
          "states:DescribeExecution",
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:states:${var.region}:${data.aws_caller_identity.current.account_id}:stateMachine:${local.lambda_name_prefix}-state-machine",
          "arn:${data.aws_partition.current.partition}:states:${var.region}:${data.aws_caller_identity.current.account_id}:execution:${local.lambda_name_prefix}-state-machine:*",
        ]
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
    Comment = "Weekly GitHub organisation policy audit (release: ${var.release_version})."
    StartAt = "PrepareInitialInput"
    States = {
      PrepareInitialInput = {
        Type = "Pass"
        Parameters = {
          "owner.$"       = "$.owner"
          "levels.$"      = "$.levels"
          "run_id.$"      = "$$.Execution.Name"
          "output_bucket" = aws_s3_bucket.audit_output.bucket
        }
        ResultPath = "$.initial_input"
        Next       = "RateLimitStart"
      }
      RateLimitStart = {
        Type     = "Task"
        Resource = aws_lambda_function.audit["rate_limit"].arn
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException",
            ]
            IntervalSeconds = 2
            BackoffRate     = 2.0
            MaxAttempts     = 3
          },
          {
            ErrorEquals = [
              "Lambda.AWSLambdaException",
              "States.TaskFailed",
            ]
            IntervalSeconds = 60
            BackoffRate     = 2.0
            MaxAttempts     = 3
            JitterStrategy  = "FULL"
          }
        ]
        Parameters = {
          "owner.$"    = "$.initial_input.owner"
          "checkpoint" = "rate-limit-start"
        }
        ResultPath = "$.rate_limit_start"
        Next       = "Initialise"
      }
      Initialise = {
        Type = "Parallel"
        Branches = [
          {
            StartAt = "list_repositories"
            States = {
              list_repositories = {
                Type     = "Task"
                Resource = aws_lambda_function.audit["list_repositories"].arn
                Retry = [
                  {
                    ErrorEquals = [
                      "Lambda.ServiceException",
                      "Lambda.SdkClientException",
                      "Lambda.TooManyRequestsException",
                    ]
                    IntervalSeconds = 2
                    BackoffRate     = 2.0
                    MaxAttempts     = 3
                  },
                  {
                    ErrorEquals = [
                      "Lambda.AWSLambdaException",
                      "States.TaskFailed",
                    ]
                    IntervalSeconds = 60
                    BackoffRate     = 2.0
                    MaxAttempts     = 3
                    JitterStrategy  = "FULL"
                  }
                ]
                Parameters = {
                  "owner.$"         = "$.initial_input.owner"
                  "run_id.$"        = "$.initial_input.run_id"
                  "output_bucket.$" = "$.initial_input.output_bucket"
                }
                End = true
              }
            }
          },
          {
            StartAt = "list_teams"
            States = {
              list_teams = {
                Type     = "Task"
                Resource = aws_lambda_function.audit["list_teams"].arn
                Retry = [
                  {
                    ErrorEquals = [
                      "Lambda.ServiceException",
                      "Lambda.SdkClientException",
                      "Lambda.TooManyRequestsException",
                    ]
                    IntervalSeconds = 2
                    BackoffRate     = 2.0
                    MaxAttempts     = 3
                  },
                  {
                    ErrorEquals = [
                      "Lambda.AWSLambdaException",
                      "States.TaskFailed",
                    ]
                    IntervalSeconds = 60
                    BackoffRate     = 2.0
                    MaxAttempts     = 3
                    JitterStrategy  = "FULL"
                  }
                ]
                Parameters = {
                  "owner.$" = "$.initial_input.owner"
                }
                End = true
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
          "owner.$"               = "$.initial_input.owner"
          "levels.$"              = "$.initial_input.levels"
          "run_id.$"              = "$.initial_input.run_id"
          "output_bucket"         = aws_s3_bucket.audit_output.bucket
          "repositories_s3_ref.$" = "$.initial_data[0]"
          "teams_s3_ref.$"        = "$.initial_data[1]"
          "rate_limit_start.$"    = "$.rate_limit_start"
        }
        ResultPath = "$"
        Next       = "OrganisationChecks"
      }
      OrganisationChecks = {
        Type = "Parallel"
        Branches = [
          for check_name in local.organisation_check_names : {
            StartAt = check_name
            States = {
              (check_name) = {
                Type     = "Task"
                Resource = aws_lambda_function.audit[check_name].arn
                Retry = [
                  {
                    ErrorEquals = [
                      "Lambda.ServiceException",
                      "Lambda.SdkClientException",
                      "Lambda.TooManyRequestsException",
                    ]
                    IntervalSeconds = 2
                    BackoffRate     = 2.0
                    MaxAttempts     = 3
                  },
                  {
                    ErrorEquals = [
                      "Lambda.AWSLambdaException",
                      "States.TaskFailed",
                    ]
                    IntervalSeconds = 60
                    BackoffRate     = 2.0
                    MaxAttempts     = 3
                    JitterStrategy  = "FULL"
                  }
                ]
                Parameters = {
                  "owner.$"  = "$.owner"
                  "levels.$" = "$.levels"
                }
                ResultSelector = {
                  "check_name.$" = "$.check_name"
                  "result.$"     = "$.result"
                  "message.$"    = "$.message"
                  "details.$"    = "$.details"
                }
                Next = "store_${check_name}"
              }
              "store_${check_name}" = {
                Type     = "Task"
                Resource = aws_lambda_function.audit["store_organisation_checks"].arn
                Retry = [
                  {
                    ErrorEquals = [
                      "Lambda.ServiceException",
                      "Lambda.AWSLambdaException",
                      "Lambda.SdkClientException",
                      "Lambda.TooManyRequestsException",
                      "States.TaskFailed",
                    ]
                    IntervalSeconds = 2
                    BackoffRate     = 2.0
                    MaxAttempts     = 3
                  }
                ]
                Parameters = {
                  "owner.$"         = "$.owner"
                  "run_id.$"        = "$.run_id"
                  "output_bucket.$" = "$.output_bucket"
                  "check_name.$"    = "$.check_name"
                  "result.$"        = "$.result"
                  "message.$"       = "$.message"
                  "details.$"       = "$.details"
                }
                ResultPath = null
                OutputPath = null
                End        = true
              }
            }
          }
        ]
        ResultPath = null
        Next       = "TeamChecksMap"
      }
      TeamChecksMap = {
        Type           = "Map"
        MaxConcurrency = var.team_map_max_concurrency
        ItemReader = {
          Resource = "arn:${data.aws_partition.current.partition}:states:::s3:getObject"
          ReaderConfig = {
            InputType = "JSON"
          }
          Parameters = {
            "Bucket.$" = "$.teams_s3_ref.s3_bucket"
            "Key.$"    = "$.teams_s3_ref.s3_key"
          }
        }
        ItemSelector = {
          "owner.$"         = "$.owner"
          "run_id.$"        = "$.run_id"
          "output_bucket.$" = "$.output_bucket"
          "team.$"          = "$$.Map.Item.Value"
        }
        ItemProcessor = {
          ProcessorConfig = {
            Mode = "INLINE"
          }
          StartAt = "TeamChecksParallel"
          States = {
            TeamChecksParallel = {
              Type = "Parallel"
              Branches = [
                for check_name in local.team_check_names : {
                  StartAt = check_name
                  States = {
                    (check_name) = {
                      Type     = "Task"
                      Resource = aws_lambda_function.audit[check_name].arn
                      Retry = [
                        {
                          ErrorEquals = [
                            "Lambda.ServiceException",
                            "Lambda.SdkClientException",
                            "Lambda.TooManyRequestsException",
                          ]
                          IntervalSeconds = 2
                          BackoffRate     = 2.0
                          MaxAttempts     = 3
                        },
                        {
                          ErrorEquals = [
                            "Lambda.AWSLambdaException",
                            "States.TaskFailed",
                          ]
                          IntervalSeconds = 60
                          BackoffRate     = 2.0
                          MaxAttempts     = 3
                          JitterStrategy  = "FULL"
                        }
                      ]
                      Parameters = {
                        "owner.$"     = "$.owner"
                        "team_slug.$" = "$.team.slug"
                      }
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
              Next       = "FormatTeamChecks"
            }
            FormatTeamChecks = {
              Type = "Pass"
              Parameters = {
                "owner.$"         = "$.owner"
                "run_id.$"        = "$.run_id"
                "output_bucket.$" = "$.output_bucket"
                "team_slug.$"     = "$.team.slug"
                "checks.$"        = "$.check_results"
              }
              Next = "store_team_checks"
            }
            store_team_checks = {
              Type     = "Task"
              Resource = aws_lambda_function.audit["store_team_checks"].arn
              Retry = [
                {
                  ErrorEquals = [
                    "Lambda.ServiceException",
                    "Lambda.AWSLambdaException",
                    "Lambda.SdkClientException",
                    "Lambda.TooManyRequestsException",
                    "States.TaskFailed",
                  ]
                  IntervalSeconds = 2
                  BackoffRate     = 2.0
                  MaxAttempts     = 3
                }
              ]
              Parameters = {
                "owner.$"         = "$.owner"
                "run_id.$"        = "$.run_id"
                "output_bucket.$" = "$.output_bucket"
                "team_slug.$"     = "$.team_slug"
                "checks.$"        = "$.checks"
              }
              ResultPath = null
              End        = true
            }
          }
        }
        Next = "RepositoryChecksMap"
      }
      RepositoryChecksMap = {
        Type           = "Map"
        MaxConcurrency = var.repository_map_max_concurrency
        ItemReader = {
          Resource = "arn:${data.aws_partition.current.partition}:states:::s3:getObject"
          ReaderConfig = {
            InputType = "JSON"
          }
          Parameters = {
            "Bucket.$" = "$.repositories_s3_ref.s3_bucket"
            "Key.$"    = "$.repositories_s3_ref.s3_key"
          }
        }
        ItemSelector = {
          "owner.$"         = "$.owner"
          "run_id.$"        = "$.run_id"
          "output_bucket.$" = "$.output_bucket"
          "repository.$"    = "$$.Map.Item.Value"
        }
        ItemProcessor = {
          ProcessorConfig = {
            Mode          = "DISTRIBUTED"
            ExecutionType = "STANDARD"
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
                      Retry = [
                        {
                          ErrorEquals = [
                            "Lambda.ServiceException",
                            "Lambda.SdkClientException",
                            "Lambda.TooManyRequestsException",
                          ]
                          IntervalSeconds = 2
                          BackoffRate     = 2.0
                          MaxAttempts     = 3
                        },
                        {
                          ErrorEquals = [
                            "Lambda.AWSLambdaException",
                            "States.TaskFailed",
                          ]
                          IntervalSeconds = 60
                          BackoffRate     = 2.0
                          MaxAttempts     = 3
                          JitterStrategy  = "FULL"
                        }
                      ]
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
                "owner.$"           = "$.owner"
                "run_id.$"          = "$.run_id"
                "output_bucket.$"   = "$.output_bucket"
                "repository_name.$" = "$.repository.name"
                "checks.$"          = "$.check_results"
              }
              Next = "store_repository_output"
            }
            store_repository_output = {
              Type     = "Task"
              Resource = aws_lambda_function.audit["store_repository_output"].arn
              Retry = [
                {
                  ErrorEquals = [
                    "Lambda.ServiceException",
                    "Lambda.AWSLambdaException",
                    "Lambda.SdkClientException",
                    "Lambda.TooManyRequestsException",
                    "States.TaskFailed",
                  ]
                  IntervalSeconds = 2
                  BackoffRate     = 2.0
                  MaxAttempts     = 3
                }
              ]
              Parameters = {
                "owner.$"           = "$.owner"
                "run_id.$"          = "$.run_id"
                "output_bucket.$"   = "$.output_bucket"
                "repository_name.$" = "$.repository_name"
                "checks.$"          = "$.checks"
              }
              ResultPath = null
              End        = true
            }
          }
        }
        ResultPath = null
        Next       = "RateLimitEnd"
      }
      RateLimitEnd = {
        Type     = "Task"
        Resource = aws_lambda_function.audit["rate_limit"].arn
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException",
            ]
            IntervalSeconds = 2
            BackoffRate     = 2.0
            MaxAttempts     = 3
          },
          {
            ErrorEquals = [
              "Lambda.AWSLambdaException",
              "States.TaskFailed",
            ]
            IntervalSeconds = 60
            BackoffRate     = 2.0
            MaxAttempts     = 3
            JitterStrategy  = "FULL"
          }
        ]
        Parameters = {
          "owner.$"    = "$.owner"
          "checkpoint" = "rate-limit-end"
        }
        ResultPath = "$.rate_limit_end"
        Next       = "store_output"
      }
      store_output = {
        Type     = "Task"
        Resource = aws_lambda_function.audit["store_output"].arn
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException",
              "States.TaskFailed",
            ]
            IntervalSeconds = 2
            BackoffRate     = 2.0
            MaxAttempts     = 3
          }
        ]
        Parameters = {
          "run_id.$"               = "$.run_id"
          "output_bucket.$"        = "$.output_bucket"
          "owner.$"                = "$.owner"
          "teams_s3_ref.$"         = "$.teams_s3_ref"
          "organisation_results.$" = "$.organisation_results"
          "rate_limit_start.$"     = "$.rate_limit_start"
          "rate_limit_end.$"       = "$.rate_limit_end"
        }
        End = true
      }
    }
  })

  tags = {
    ReleaseVersion = var.release_version
  }

  tracing_configuration {
    enabled = true
  }

  logging_configuration {
    level                  = "ALL"
    include_execution_data = true
    log_destination        = "${aws_cloudwatch_log_group.step_function.arn}:*"
  }
}
