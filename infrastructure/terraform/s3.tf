# S3 Bucket for templates
resource "aws_s3_bucket" "templates" {
  bucket = "showspec-cad-bench-templates-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "showspec-cad-bench-templates"
  }
}

# Enable versioning
resource "aws_s3_bucket_versioning" "templates" {
  bucket = aws_s3_bucket.templates.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "templates" {
  bucket = aws_s3_bucket.templates.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "templates" {
  bucket = aws_s3_bucket.templates.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
