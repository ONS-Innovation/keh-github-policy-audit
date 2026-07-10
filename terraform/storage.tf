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
