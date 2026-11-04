resource "aws_db_subnet_group" "main" {
  count      = var.enable_rds ? 1 : 0
  name       = "${var.project}-rds"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_db_instance" "mysql" {
  count                       = var.enable_rds ? 1 : 0
  identifier                  = "${var.project}-mysql"
  engine                      = "mysql"
  engine_version              = "8.0"
  instance_class              = "db.t3.micro"
  allocated_storage           = 20
  db_name                     = "source"
  username                    = "admin"
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.main[0].name
  vpc_security_group_ids      = [aws_security_group.databases.id]
  publicly_accessible         = false
  multi_az                    = false
  storage_encrypted           = true
  backup_retention_period     = 1
  skip_final_snapshot         = true
}