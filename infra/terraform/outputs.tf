output "bucket_name" {
  value = aws_s3_bucket.dw.bucket
}
output "redshift_endpoint" {
  value = try(aws_redshiftserverless_workgroup.dw[0].endpoint[0].address, null)
}
output "rds_endpoint" {
  value = try(aws_db_instance.mysql[0].address, null)
}
output "docdb_endpoint" {
  value = try(aws_docdb_cluster.main[0].endpoint, null)
}
output "ec2_public_ip" {
  value = try(aws_instance.airflow[0].public_ip, null)
}
output "redshift_admin_secret_arn" {
  value = try(aws_redshiftserverless_namespace.dw[0].admin_password_secret_arn, null)
}
output "rds_admin_secret_arn" {
  value = try(aws_db_instance.mysql[0].master_user_secret[0].secret_arn, null)
}
output "redshift_role_arn" {
  value = aws_iam_role.redshift_s3.arn
}

