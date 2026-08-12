resource "aws_s3_bucket" "audit_output" {
  bucket = local.audit_output_bucket
}

resource "aws_s3_bucket_public_access_block" "audit_output" {
  bucket                  = aws_s3_bucket.audit_output.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "audit_output" {
  bucket = aws_s3_bucket.audit_output.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "audit_output" {
  bucket = aws_s3_bucket.audit_output.id

  rule {
    id     = "expire-audit-runs"
    status = "Enabled"

    filter {
      prefix = "audit-runs/"
    }

    expiration {
      days = var.audit_run_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.audit_run_retention_days
    }
  }

  rule {
    id     = "expire-audit-summaries"
    status = "Enabled"

    filter {
      prefix = "audit-results/"
    }

    expiration {
      days = var.audit_summary_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.audit_summary_retention_days
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_object" "scorecard_criteria" {
  bucket       = aws_s3_bucket.audit_output.id
  key          = local.scorecard_config_s3_key
  source       = "${path.module}/../config/scorecard_criteria.json"
  etag         = filemd5("${path.module}/../config/scorecard_criteria.json")
  content_type = "application/json"

  lifecycle {
    ignore_changes = [
      source,
      etag,
    ]
  }
}

resource "aws_s3_object" "dependency_layer" {
  bucket = aws_s3_bucket.audit_output.id
  key    = local.dependency_layer_s3_key
  source = "${path.module}/../build/dependency-layer.zip"
  etag   = filemd5("${path.module}/../build/dependency-layer.zip")
}
