"""Ejecuta comandos de dbt (contra Redshift) desde tareas de Airflow.

Cambios frente a la versión local:
- Ya no hay archivo DuckDB que proteger: se elimina el bloqueo con fcntl.
  Redshift admite conexiones concurrentes; el orden lo da el DAG.
- Las rutas salen de variables de entorno (DBT_EXECUTABLE, DBT_PROJECT) para no fijar /home/airflow.
- La conexión usa REDSHIFT_HOST/DB/USER/PASSWORD, que lee src/dbt/profiles.yml.
"""

import logging
import os
import subprocess
from pathlib import Path

DBT_EXECUTABLE = os.getenv("DBT_EXECUTABLE", str(Path.home() / "dbt-venv" / "bin" / "dbt"))
DBT_PROJECT = Path(os.getenv("DBT_PROJECT", str(Path.home() / "DE-DW" / "src" / "dbt")))
LOGGER = logging.getLogger(__name__)


def run_dbt(command, selector=None):
    """Ejecuta un comando de dbt y falla la tarea si dbt devuelve error."""
    arguments = [
        DBT_EXECUTABLE,
        command,
        "--project-dir", str(DBT_PROJECT),
        "--profiles-dir", str(DBT_PROJECT),
    ]
    if selector is not None:
        arguments.extend(["--select", selector])
    LOGGER.info("Running dbt command: %s", " ".join(arguments))
    # dbt escribe su salida en el log de la tarea; check=True convierte el código de error en excepción.
    subprocess.run(arguments, check=True)
