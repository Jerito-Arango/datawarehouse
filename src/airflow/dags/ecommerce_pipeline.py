"""DAG único del Data Warehouse en AWS: validar, elegir lote, extraer a S3, cargar a Redshift, dbt y reconciliar.

Sustituye a los tres DAGs locales (ecommerce_pipeline + extract_to_raw + transform_warehouse): con
SQLite y SequentialExecutor, un DAG que espera a otro con TriggerDagRunOperator se bloquearía,
porque la tarea que espera ocupa la única ranura de ejecución. Un solo DAG evita eso.

Disparo manual (o diario 06:00 si se activa). Configuración opcional del run: {"batch_id": "003"}.
Demo de fallo: Variable simulate_failure = load_to_redshift (o extract_to_s3).
"""

from datetime import timedelta

import pendulum
from airflow.operators.python import PythonOperator

from airflow import DAG
from ecommerce_dw.ingestion import pipeline_tasks as tasks
from ecommerce_dw.transformations.dbt_runner import run_dbt

default_args = {
    # Tres intentos en total: la tarea reintenta dos veces ante fallos transitorios.
    "retries": 2,
    "retry_delay": timedelta(seconds=30),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="ecommerce_pipeline",
    description="MySQL + DocumentDB -> S3 -> Redshift -> dbt (snapshots, marts, tests)",
    start_date=pendulum.datetime(2025, 1, 1, tz="America/Bogota"),
    schedule="0 6 * * *",
    catchup=False,
    # Nace en pausa: el diario solo corre cuando el usuario lo activa; el disparo manual funciona igual.
    is_paused_upon_creation=True,
    max_active_runs=1,
    max_active_tasks=1,
    default_args=default_args,
    tags=["dw", "aws"],
) as dag:
    validate = PythonOperator(task_id="validate_environment", python_callable=tasks.validate_environment)

    batch = PythonOperator(
        task_id="resolve_batch_id",
        python_callable=tasks.resolve_batch_id,
        # dag_run.conf permite fijar el lote al disparar a mano; vacío = automático.
        op_kwargs={"requested": "{{ dag_run.conf.get('batch_id', '') if dag_run and dag_run.conf else '' }}"},
    )
    # El id del lote viaja por XCom: los reintentos y las tareas siguientes usan siempre el mismo.
    batch_id = "{{ ti.xcom_pull(task_ids='resolve_batch_id') }}"

    extract = PythonOperator(task_id="extract_to_s3", python_callable=tasks.extract, op_args=[batch_id])
    load = PythonOperator(task_id="load_to_redshift", python_callable=tasks.load, op_args=[batch_id])

    deps = PythonOperator(task_id="dbt_deps", python_callable=run_dbt, op_args=["deps"])
    seed = PythonOperator(task_id="dbt_seed", python_callable=run_dbt, op_args=["seed"])
    intermediate = PythonOperator(task_id="dbt_run_intermediate", python_callable=run_dbt,
                                  op_args=["run", "path:models/intermediate"])
    quarantine = PythonOperator(task_id="dbt_run_quarantine", python_callable=run_dbt,
                                op_args=["run", "path:models/quarantine"])
    snapshots = PythonOperator(task_id="dbt_snapshot", python_callable=run_dbt, op_args=["snapshot"])
    marts = PythonOperator(task_id="dbt_run_marts", python_callable=run_dbt, op_args=["run", "path:models/marts"])
    dbt_tests = PythonOperator(task_id="dbt_test", python_callable=run_dbt, op_args=["test"])

    reconcile = PythonOperator(task_id="reconcile_batch", python_callable=tasks.reconcile, op_args=[batch_id])

    (validate >> batch >> extract >> load >> deps >> seed >> intermediate >> quarantine
     >> snapshots >> marts >> dbt_tests >> reconcile)
