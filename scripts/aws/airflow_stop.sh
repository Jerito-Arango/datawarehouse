#!/usr/bin/env bash
# Detiene Airflow en la EC2.
pkill -f "airflow-venv|airflow-webserver" && echo "Airflow detenido" || echo "Airflow no estaba corriendo"
