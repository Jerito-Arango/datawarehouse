data "aws_caller_identity" "me" {}

resource "aws_s3_bucket" "dw" {
  bucket        = "${var.project}-${data.aws_caller_identity.me.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "dw" {
  bucket                  = aws_s3_bucket.dw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "dw" {
  bucket = aws_s3_bucket.dw.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dw" {
  bucket = aws_s3_bucket.dw.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}