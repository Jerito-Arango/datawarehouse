resource "aws_docdb_subnet_group" "main" {
  count      = var.enable_docdb ? 1 : 0
  name       = "${var.project}-docdb"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_docdb_cluster" "main" {
  count                   = var.enable_docdb ? 1 : 0
  cluster_identifier      = "${var.project}-docdb"
  engine                  = "docdb"
  master_username         = "docdbadmin"
  master_password         = var.docdb_password
  db_subnet_group_name    = aws_docdb_subnet_group.main[0].name
  vpc_security_group_ids  = [aws_security_group.databases.id]
  storage_encrypted       = true
  backup_retention_period = 1
  skip_final_snapshot     = true
  lifecycle {
    ignore_changes = [master_password]
  }
}

resource "aws_docdb_cluster_instance" "main" {
  count              = var.enable_docdb ? 1 : 0
  identifier         = "${var.project}-docdb-1"
  cluster_identifier = aws_docdb_cluster.main[0].id
  instance_class     = "db.t3.medium"
}