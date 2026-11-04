data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

resource "aws_key_pair" "main" {
  count      = var.enable_ec2 ? 1 : 0
  key_name   = "${var.project}-key"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "aws_instance" "airflow" {
  count                  = var.enable_ec2 ? 1 : 0
  ami                    = data.aws_ami.al2023.id
  instance_type          = "t3.medium" # Airflow + dbt necesitan ~4 GB de RAM
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = aws_key_pair.main[0].key_name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }
  metadata_options {
    http_tokens = "required"
  }
  tags = { Name = "${var.project}-airflow" }
}