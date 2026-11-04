# Rol que Redshift usa para leer S3 con COPY
resource "aws_iam_role" "redshift_s3" {
  name = "${var.project}-redshift-s3"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = ["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"]
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "redshift_s3" {
  name = "leer-bucket-dw"
  role = aws_iam_role.redshift_s3.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.dw.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = aws_s3_bucket.dw.arn
      }
    ]
  })
}

# Rol de la EC2 (Airflow + dbt): lee y escribe en el bucket
resource "aws_iam_role" "ec2" {
  name = "${var.project}-ec2"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ec2_s3" {
  name = "rw-bucket-dw"
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.dw.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.dw.arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project}-ec2"
  role = aws_iam_role.ec2.name
}


resource "aws_iam_role_policy" "ec2_secrets" {
  count = var.enable_rds || var.enable_redshift ? 1 : 0
  name  = "leer-secretos-dw"
  role  = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = compact([
        try(aws_db_instance.mysql[0].master_user_secret[0].secret_arn, ""),
        try(aws_redshiftserverless_namespace.dw[0].admin_password_secret_arn, ""),
      ])
    }]
  })
}