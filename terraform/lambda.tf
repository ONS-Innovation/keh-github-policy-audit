resource "aws_security_group" "lambda_sg" {
  name        = "${local.lambda_name_prefix}-sg"
  description = "Security group for ${local.lambda_name_prefix} Lambda function"
  vpc_id      = data.terraform_remote_state.vpc.outputs.vpc_id
  ingress {
    description = "Allow inbound HTTPS traffic from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"] // Allow HTTPS traffic within VPC
  }
  egress {
    description = "Allow all outbound HTTPS traffic to any destination"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"] // Allow all outbound traffic
  }
}

resource "aws_iam_role" "lambda_execution" {
  name = "${local.lambda_name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_access_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "${local.lambda_name_prefix}-permissions"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowGitHubSecretsRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.github_app_id_secret_name}*",
          "arn:${data.aws_partition.current.partition}:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.github_private_key_secret_name}*",
        ]
      },
      {
        Sid    = "AllowStoreOutputWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
        ]
        Resource = "${aws_s3_bucket.audit_output.arn}/*"
      },
      {
        Sid    = "AllowStoreOutputList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
        ]
        Resource = aws_s3_bucket.audit_output.arn
      },
    ]
  })
}

resource "aws_lambda_layer_version" "dependencies" {
  filename            = "${path.module}/../build/dependency-layer.zip"
  source_code_hash    = filebase64sha256("${path.module}/../build/dependency-layer.zip")
  layer_name          = "${local.lambda_name_prefix}-dependencies"
  compatible_runtimes = [var.lambda_runtime]
}

resource "aws_cloudwatch_log_group" "audit" {
  for_each = local.lambda_definitions

  name              = "/aws/lambda/${local.lambda_name_prefix}-${replace(each.key, "_", "-")}"
  retention_in_days = var.lambda_log_retention_days
}

resource "aws_lambda_function" "audit" {
  for_each = local.lambda_definitions

  function_name = "${local.lambda_name_prefix}-${replace(each.key, "_", "-")}"
  role          = aws_iam_role.lambda_execution.arn
  runtime       = var.lambda_runtime
  handler       = each.value.handler
  filename      = each.value.zip_path

  source_code_hash               = filebase64sha256(each.value.zip_path)
  timeout                        = try(each.value.timeout, var.lambda_timeout)
  memory_size                    = var.lambda_memory_size
  reserved_concurrent_executions = var.lambda_reserved_concurrent_executions
  layers                         = [aws_lambda_layer_version.dependencies.arn]

  vpc_config {
    subnet_ids         = data.terraform_remote_state.vpc.outputs.private_subnets
    security_group_ids = [aws_security_group.lambda_sg.id] // Dedicated security group for Lambda function
  }

  tracing_config {
    mode = "Active"
  }

  logging_config {
    log_format = "JSON"
  }

  depends_on = [aws_cloudwatch_log_group.audit]

  environment {
    variables = {
      ENVIRONMENT                    = "prod"
      APP_LOG_FORMAT                 = "JSON"
      S3_BUCKET_NAME                 = aws_s3_bucket.audit_output.bucket
      GITHUB_APP_ID_SECRET_NAME      = var.github_app_id_secret_name
      GITHUB_PRIVATE_KEY_SECRET_NAME = var.github_private_key_secret_name
    }
  }
}
