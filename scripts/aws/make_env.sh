#!/usr/bin/env bash
# Genera .env.aws (direcciones y ARN, sin contraseñas) a partir de los outputs de Terraform.
# Uso, desde la raíz del repo, en tu computador: scripts/aws/make_env.sh <carpeta-de-terraform>
set -euo pipefail
TF_DIR="${1:?Uso: $0 <carpeta-de-terraform>}"

out() {
  local value
  value="$(terraform -chdir="$TF_DIR" output -raw "$1" 2>/dev/null)" || value=""
  if [ -z "$value" ]; then
    echo "ERROR: Terraform no tiene el output '$1'. ¿Terminó 'terraform apply' en $TF_DIR?" >&2
    exit 1
  fi
  printf '%s' "$value"
}

# Se leen todos antes de escribir nada: si uno falla, no queda un .env.aws a medias.
BUCKET="$(out bucket_name)"
RDS="$(out rds_endpoint)"
DOCDB="$(out docdb_endpoint)"
REDSHIFT="$(out redshift_endpoint)"
ROLE="$(out redshift_role_arn)"
RDS_SECRET="$(out rds_admin_secret_arn)"
REDSHIFT_SECRET="$(out redshift_admin_secret_arn)"
IP="$(out ec2_public_ip)"

cat > .env.aws <<ENV
AWS_DEFAULT_REGION=us-east-2
S3_BUCKET=$BUCKET
RDS_ENDPOINT=$RDS
DOCDB_ENDPOINT=$DOCDB
REDSHIFT_ENDPOINT=$REDSHIFT
REDSHIFT_ROLE_ARN=$ROLE
RDS_SECRET_ARN=$RDS_SECRET
REDSHIFT_SECRET_ARN=$REDSHIFT_SECRET
EC2_PUBLIC_IP=$IP
ENV
echo ".env.aws generado (sin contraseñas). No lo subas a Git."