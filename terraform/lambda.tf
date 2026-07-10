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
        ]
        Resource = "${aws_s3_bucket.audit_output.arn}/*"
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

resource "aws_lambda_function" "audit" {
  for_each = local.lambda_definitions

  function_name = "${local.lambda_name_prefix}-${replace(each.key, "_", "-")}"
  role          = aws_iam_role.lambda_execution.arn
  runtime       = var.lambda_runtime
  handler       = each.value.handler
  filename      = each.value.zip_path

  source_code_hash = filebase64sha256(each.value.zip_path)
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size
  layers           = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      ENVIRONMENT                    = "prod"
      S3_BUCKET_NAME                 = aws_s3_bucket.audit_output.bucket
      GITHUB_APP_ID_SECRET_NAME      = var.github_app_id_secret_name
      GITHUB_PRIVATE_KEY_SECRET_NAME = var.github_private_key_secret_name
    }
  }
}
