# Orquestación con Airflow en la EC2 (sección 3.4)

## Qué se instala y dónde
- Airflow 2.11.2 en `~/airflow-venv`, con SQLite y SequentialExecutor (una sola máquina, una tarea a la vez).
- dbt en `~/dbt-venv` (aparte, para que sus dependencias no choquen con las de Airflow).
- Airflow arranca con `scripts/aws/airflow_start.sh`, que carga antes el entorno (`aws_env.sh`): las tareas heredan
  `S3_BUCKET`, `MYSQL_*`, `MONGODB_URI` y `REDSHIFT_*`. Ningún secreto se guarda en el repo.
- Interfaz en `http://<ip-ec2>:8080`, abierta solo a la IP del estudiante por el grupo de seguridad.

## Un solo DAG: `ecommerce_pipeline`
`validate_environment → resolve_batch_id → extract_to_s3 → load_to_redshift → dbt_deps → dbt_seed →
dbt_run_intermediate → dbt_run_quarantine → dbt_snapshot → dbt_run_marts → dbt_test → reconcile_batch`

Diferencia con el proyecto local: allí eran tres DAGs y el maestro esperaba a los otros con `TriggerDagRunOperator`.
Con SQLite y SequentialExecutor la tarea que espera ocupa la única ranura y el DAG hijo nunca arranca, así que se unificó.
Los DAGs locales (`extract_to_raw.py`, `transform_warehouse.py`) siguen en el repo pero Airflow los ignora (`.airflowignore`),
porque dependen de DuckDB.

Reintentos: dos reintentos por tarea, 30 s de espera con retroceso exponencial (máximo 5 min). Registro: el log de cada
tarea queda en `~/airflow/logs` y se ve en la interfaz.

## Cómo se identifica un lote procesado y cuándo se actualiza su marca
- **S3:** `raw/<fuente>/<entidad>/batch_id=<id>/_manifest.json`. Se escribe al final de la extracción de esa entidad,
  después del CSV. Si existe, el lote de esa entidad está completo y no se vuelve a extraer ni se sobrescribe.
- **Redshift:** `"raw".batch_control` (una fila por fuente, entidad y lote, con filas esperadas, cargadas y `status='loaded'`).
  Se inserta en la misma transacción que los datos: si el conteo cargado no coincide con el manifiesto, se hace rollback
  y no queda marca.
- `resolve_batch_id` usa las dos marcas: abre un lote nuevo solo si el último está completo en S3 **y** cargado en Redshift;
  si no, retoma ese mismo lote. Así nunca avanza la marca de agua de la extracción sin haber cargado los datos.

## Demostración de fallo y reintento
1. Interfaz → Admin → Variables → crear `simulate_failure` = `load_to_redshift`.
2. Disparar el DAG. `extract_to_s3` termina; `load_to_redshift` falla en sus tres intentos y las tareas siguientes quedan en `upstream_failed`.
3. Cambiar la Variable a vacío (o borrarla), abrir la tarea fallida y pulsar **Clear**. Se reintenta solo desde esa tarea,
   con el mismo lote (el id viaja por XCom), y la extracción no se repite.
