#!/usr/bin/env bash
# Instala Airflow en la EC2 (una vez). Usa SQLite y SequentialExecutor: suficiente para una sola máquina.
# Uso, desde tu computador: ssh -i ~/.ssh/dw-user10 ec2-user@<ip> 'bash -s' < scripts/aws/airflow_install.sh
set -euo pipefail
AIRFLOW_VERSION=2.11.2
PYTHON_VERSION=3.11
[ -d "$HOME/airflow-venv" ] || python3.11 -m venv "$HOME/airflow-venv"
# El archivo de constraints fija versiones compatibles de las dependencias de Airflow.
"$HOME/airflow-venv/bin/pip" install -q "apache-airflow==${AIRFLOW_VERSION}" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
# Librerías que usan las tareas (Airflow ejecuta el código del repo con su propio Python).
"$HOME/airflow-venv/bin/pip" install -q PyMySQL==1.1.2 pymongo==4.16.0 boto3 redshift_connector
echo "Airflow instalado en ~/airflow-venv"
