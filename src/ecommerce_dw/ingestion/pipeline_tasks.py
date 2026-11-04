"""Tareas del DAG de AWS: validar entorno, elegir lote, extraer a S3, cargar a Redshift y reconciliar.

Marca de lote procesado (sección 3.5):
- S3: raw/<fuente>/<entidad>/batch_id=<id>/_manifest.json existe  => el lote se extrajo completo.
- Redshift: "raw".batch_control tiene status='loaded' para las seis entidades del lote
  => el lote se cargó completo. Se escribe en la MISMA transacción que los datos.
Un lote se considera terminado solo con las dos marcas; si falta alguna, el siguiente
run retoma ese mismo lote en vez de abrir uno nuevo.
"""

import logging
import os
import re

import boto3

from .redshift_load import RAW_TABLES, connect as redshift_connect, load_batch
from .s3_extract import extract_to_s3

LOGGER = logging.getLogger(__name__)
REQUIRED_ENV = ["S3_BUCKET", "MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MONGODB_URI", "REDSHIFT_HOST"]
ENTITIES = list(RAW_TABLES)  # [(fuente, entidad), ...] las seis entidades


def _bucket():
    return os.environ["S3_BUCKET"]


def maybe_fail(task_id):
    """Para la demo de fallo y reintento: si la Variable de Airflow 'simulate_failure' vale el task_id, falla."""
    from airflow.models import Variable

    if Variable.get("simulate_failure", default_var="") == task_id:
        raise RuntimeError(f"Fallo simulado en {task_id} (Variable simulate_failure). Quítala y reintenta la tarea.")


def validate_environment():
    """Falla pronto, con un mensaje claro, si falta una variable o no hay conexión a algún servicio."""
    problems = []
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if not (os.getenv("REDSHIFT_PASSWORD") or os.getenv("REDSHIFT_SECRET_ARN")):
        missing.append("REDSHIFT_PASSWORD o REDSHIFT_SECRET_ARN")
    if missing:
        raise EnvironmentError(f"Faltan variables de entorno: {', '.join(missing)}")

    try:
        boto3.client("s3").head_bucket(Bucket=_bucket())
    except Exception as error:  # noqa: BLE001 - se informa cualquier causa
        problems.append(f"S3 {_bucket()}: {error}")
    try:
        from .raw_sources import connect_mysql

        connection = connect_mysql()
        connection.cursor().execute("SELECT 1")
        connection.close()
    except Exception as error:  # noqa: BLE001
        problems.append(f"MySQL (RDS): {error}")
    try:
        from pymongo import MongoClient

        client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        client.close()
    except Exception as error:  # noqa: BLE001
        problems.append(f"DocumentDB: {error}")
    try:
        connection = redshift_connect()
        connection.cursor().execute("SELECT 1")
        connection.close()
    except Exception as error:  # noqa: BLE001
        problems.append(f"Redshift: {error}")

    if problems:
        raise ConnectionError("Validación del entorno fallida:\n- " + "\n- ".join(problems))
    LOGGER.info("Entorno validado: S3, MySQL, DocumentDB y Redshift responden")


def _s3_batches(s3):
    """Ids numéricos de lote presentes en S3 y, por lote, en cuántas entidades tiene manifiesto."""
    found = {}
    for source, entity in ENTITIES:
        prefix = f"raw/{source}/{entity}/"
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=_bucket(), Prefix=prefix, Delimiter="/"):
            for common in page.get("CommonPrefixes", []):
                match = re.search(r"batch_id=(\d+)/$", common["Prefix"])
                if match:
                    batch_id = match.group(1)
                    key = f"{common['Prefix']}_manifest.json"
                    try:
                        s3.head_object(Bucket=_bucket(), Key=key)
                        found[batch_id] = found.get(batch_id, 0) + 1
                    except s3.exceptions.ClientError:
                        found.setdefault(batch_id, 0)
    return found


def _loaded_entities(batch_id):
    connection = redshift_connect()
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM "raw".batch_control WHERE batch_id = %s AND status = \'loaded\'', (batch_id,))
        return cursor.fetchone()[0]
    except Exception:  # noqa: BLE001 - la tabla aún no existe (primera ejecución)
        return 0
    finally:
        connection.close()


def resolve_batch_id(requested=None):
    """Elige el lote de esta corrida.

    - Si se pasa batch_id en la configuración del run, se usa ese.
    - Si no: el siguiente número, salvo que el último lote de S3 esté incompleto o sin cargar;
      en ese caso se retoma, para no avanzar la marca de agua sin haber cargado los datos.
    """
    if requested:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(requested)):
            raise ValueError("batch_id solo admite letras, números, _ y -")
        LOGGER.info("Lote indicado por el usuario: %s", requested)
        return str(requested)
    batches = _s3_batches(boto3.client("s3"))
    if not batches:
        LOGGER.info("No hay lotes previos: extracción inicial, lote 000")
        return "000"
    last = max(batches, key=int)
    complete_in_s3 = batches[last] == len(ENTITIES)
    loaded = _loaded_entities(last) == len(ENTITIES)
    if complete_in_s3 and loaded:
        chosen = f"{int(last) + 1:03d}"
        LOGGER.info("Último lote %s completo y cargado; lote nuevo: %s", last, chosen)
    else:
        chosen = last
        LOGGER.warning("Último lote %s sin terminar (S3 completo=%s, cargado=%s); se retoma", last, complete_in_s3, loaded)
    return chosen


def extract(batch_id):
    maybe_fail("extract_to_s3")
    results = extract_to_s3(batch_id, _bucket())
    summary = [{"entity": f"{m['source']}.{m['entity']}", "rows": m["rows"], "mode": m["mode"],
                "skipped": bool(m.get("skipped"))} for m in results]
    for item in summary:
        LOGGER.info("extracción %s: %s", batch_id, item)
    return summary


def load(batch_id):
    maybe_fail("load_to_redshift")
    results = load_batch(batch_id, _bucket())
    for source, entity, expected, loaded in results:
        LOGGER.info("carga %s %s.%s: esperadas=%s cargadas=%s", batch_id, source, entity, expected, loaded)
    return [list(row) for row in results]


def reconcile(batch_id):
    """Comprueba que lo que llegó a raw se acaba de repartir entre válidos y cuarentena, y que el lote está marcado."""
    connection = redshift_connect()
    try:
        cursor = connection.cursor()

        def scalar(sql, params=None):
            cursor.execute(sql, params or ())
            return cursor.fetchone()[0]

        loaded = scalar("SELECT COUNT(*) FROM \"raw\".batch_control WHERE batch_id = %s AND status = 'loaded'", (batch_id,))
        if loaded != len(ENTITIES):
            raise ValueError(f"Lote {batch_id}: batch_control marca {loaded} de {len(ENTITIES)} entidades como cargadas")
        problems = []
        keys = {"customers": "customer_id", "products": "product_id", "orders": "order_id", "order_items": "order_item_id"}
        for entity, key in keys.items():
            # Lo recibido en raw (llaves distintas + filas sin llave) debe repartirse entre válidas y cuarentena.
            expected = scalar(
                f'SELECT COUNT(DISTINCT {key}) + SUM(CASE WHEN {key} IS NULL THEN 1 ELSE 0 END) FROM "raw".mysql_{entity}')
            valid = scalar(f"SELECT COUNT(*) FROM intermediate.int_mysql__{entity}__valid")
            quarantined = scalar(f"SELECT COUNT(*) FROM quarantine.quarantine_mysql__{entity}")
            LOGGER.info("%s: raw(llaves)=%s válidas=%s cuarentena=%s", entity, expected, valid, quarantined)
            if expected != valid + quarantined:
                problems.append(f"{entity}: raw {expected} != válidas {valid} + cuarentena {quarantined}")
        sales = scalar("SELECT COUNT(*) FROM marts.fct_sales")
        valid_items = scalar("SELECT COUNT(*) FROM intermediate.int_mysql__order_items__valid")
        LOGGER.info("fct_sales=%s, order_items válidos=%s", sales, valid_items)
        if problems:
            raise ValueError("Reconciliación fallida: " + "; ".join(problems))
        return {"batch_id": batch_id, "fct_sales": sales, "order_items_validos": valid_items}
    finally:
        connection.close()
