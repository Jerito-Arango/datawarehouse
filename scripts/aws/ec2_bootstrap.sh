#!/usr/bin/env bash
# Prepara la EC2 (una vez por máquina nueva): Python, entornos virtuales, librerías y certificado de DocumentDB.
# Uso, desde tu computador: ssh -i ~/.ssh/dw-user10 ec2-user@<ip> 'bash -s' < scripts/aws/ec2_bootstrap.sh
set -euo pipefail
sudo dnf install -y -q git python3.11 python3.11-pip mariadb105
[ -d "$HOME/venv" ] || python3.11 -m venv "$HOME/venv"
"$HOME/venv/bin/pip" install -q Faker==37.0.0 PyMySQL==1.1.2 pymongo==4.16.0 boto3 redshift_connector
[ -d "$HOME/dbt-venv" ] || python3.11 -m venv "$HOME/dbt-venv"
"$HOME/dbt-venv/bin/pip" install -q "dbt-core>=1.9,<1.10" "dbt-redshift>=1.9,<1.10"
[ -f "$HOME/global-bundle.pem" ] || curl -sSo "$HOME/global-bundle.pem" https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
echo "EC2 lista: ~/venv (extracción y carga), ~/dbt-venv (dbt) y ~/global-bundle.pem"
