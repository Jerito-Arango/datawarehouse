resource "aws_redshiftserverless_namespace" "dw" {
  count                 = var.enable_redshift ? 1 : 0
  namespace_name        = "${var.project}-ns"
  db_name               = "dw"
  admin_username        = "dwadmin"
  manage_admin_password = true # la contraseña queda en Secrets Manager
  iam_roles             = [aws_iam_role.redshift_s3.arn]
  default_iam_role_arn  = aws_iam_role.redshift_s3.arn
  # La política de lectura del bucket debe existir antes de que el rol se use en un COPY.
  depends_on = [aws_iam_role_policy.redshift_s3]
}

resource "aws_redshiftserverless_workgroup" "dw" {
  count               = var.enable_redshift ? 1 : 0
  namespace_name      = aws_redshiftserverless_namespace.dw[0].namespace_name
  workgroup_name      = "${var.project}-wg"
  base_capacity       = var.redshift_base_capacity
  subnet_ids          = data.aws_subnets.default.ids
  security_group_ids  = [aws_security_group.redshift.id]
  publicly_accessible = false

}