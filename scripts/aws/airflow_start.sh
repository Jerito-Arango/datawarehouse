#!/usr/bin/env bash
# Arranca Airflow (webserver + scheduler) en segundo plano en la EC2, con el entorno de AWS cargado.
# Uso, desde ~/DE-DW en la EC2:  bash scripts/aws/airflow_start.sh   (pide la contraseña de DocumentDB)
set -euo pipefail
cd "$(dirname "$0")/../.."
# Carga S3_BUCKET, MYSQL_*, MONGODB_URI, REDSHIFT_*: las tareas heredan estas variables.
# shellcheck disable=SC1091
source scripts/aws/aws_env.sh
export AIRFLOW_HOME="$HOME/airflow"
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/src/airflow/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export DBT_EXECUTABLE="$HOME/dbt-venv/bin/dbt" DBT_PROJECT="$PWD/src/dbt"
pkill -f "airflow-venv|airflow-webserver" 2>/dev/null || true  # el patrón no coincide con el nombre de este script
# setsid + nohup: sigue corriendo si cierras la sesión SSH.
setsid nohup "$HOME/airflow-venv/bin/airflow" standalone > "$HOME/airflow-standalone.log" 2>&1 &
echo "Airflow arrancando. Espera ~1 minuto y abre http://${EC2_PUBLIC_IP}:8080"
echo "Usuario: admin. Contraseña: cat ~/airflow/standalone_admin_password.txt"
