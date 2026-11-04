#!/usr/bin/env bash
# Copia el repo (sin .git, estado de Terraform ni secretos) y .env.aws a la EC2.
# Uso, desde la raíz del repo: scripts/aws/sync_to_ec2.sh [<ip-ec2>]   (por defecto, la de .env.aws)
set -euo pipefail
KEY="${SSH_KEY:-$HOME/.ssh/dw-user10}"
IP="${1:-$(grep '^EC2_PUBLIC_IP=' .env.aws | cut -d= -f2)}"
COPYFILE_DISABLE=1 tar czf - \
  --exclude='.git' --exclude='warehouse' --exclude='env_file' --exclude='docker/.env' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='dbt_packages' --exclude='target' \
  --exclude='.terraform' --exclude='terraform.tfstate*' --exclude='*.tfvars' . \
  | ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "ec2-user@$IP" \
      'mkdir -p ~/DE-DW && tar xzf - -C ~/DE-DW'
echo "Repo copiado a ec2-user@$IP:~/DE-DW"
