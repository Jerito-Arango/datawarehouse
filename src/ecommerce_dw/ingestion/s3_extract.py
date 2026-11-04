"""Extracción de MySQL (RDS) y MongoDB (DocumentDB) hacia S3, por lote (sección 3.2).

Diseño:
- Ruta:    raw/<fuente>/<entidad>/batch_id=<id>/<entidad>.csv  + _manifest.json
- El _manifest.json es la MARCA de lote terminado: se escribe al final, después del CSV.
  Si existe, el lote no se vuelve a extraer (idempotente) y nunca se sobrescribe.
- La marca de avance (watermark) es el mayor `watermark_to` entre los manifiestos de la entidad.
- Sin manifiesto previo => extracción inicial (completa). Con manifiesto => incremental.
"""

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from pymongo import MongoClient

from .raw_sources import BATCH_SIZE, connect_mysql, flatten_mongo

LOGGER = logging.getLogger(__name__)

# Orden de columnas del CSV (contrato con redshift_load.py y con los modelos dbt).
MYSQL_CSV_COLUMNS = {
    "customers": ["customer_id", "name", "email", "phone", "city", "department", "registration_date", "updated_at"],
    "products": ["product_id", "name", "category", "price", "description", "is_active", "updated_at"],
    "orders": ["order_id", "customer_id", "order_date", "status", "sales_channel", "payment_method", "total"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "subtotal"],
}
MONGO_CSV_COLUMNS = {
    "reviews": ["review_id", "customer_id", "product_id", "rating", "reviewed_at", "document_json"],
    "navigation_events": ["event_id", "event_type", "occurred_at", "customer_id", "product_id", "sales_channel", "document_json"],
}


def _csv_value(value):
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _write_csv(path, headers, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        count = 0
        for row in rows:
            writer.writerow([_csv_value(value) for value in row])
            count += 1
    return count


# Columna que decide "qué es nuevo" en cada entidad.
WATERMARK_COLUMN = {
    ("mysql", "customers"): "updated_at",
    ("mysql", "products"): "updated_at",
    ("mysql", "orders"): "order_id",
    ("mysql", "order_items"): "order_item_id",
    ("mongo", "reviews"): "review_id",
    ("mongo", "navigation_events"): "event_id",
}


def _parse(column, value):
    if value is None:
        return None
    return datetime.fromisoformat(value) if column.endswith("_at") else int(value)


def _dump(value):
    if value is None:
        return None
    return value.isoformat(sep=" ") if isinstance(value, datetime) else int(value)


def _prefix(source, entity, batch_id=None):
    base = f"raw/{source}/{entity}/"
    return base if batch_id is None else f"{base}batch_id={batch_id}/"


def _exists(s3, bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def _previous_watermark(s3, bucket, source, entity):
    """Mayor `watermark_to` entre los manifiestos de la entidad (None si no hay ninguno).

    Se toma el máximo, no "el último escrito": S3 guarda LastModified con resolución de
    1 segundo y dos lotes seguidos pueden empatar.
    """
    column = WATERMARK_COLUMN[(source, entity)]
    best = None
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=_prefix(source, entity)):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith("/_manifest.json"):
                manifest = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
                value = _parse(column, manifest.get("watermark_to"))
                if value is not None and (best is None or value > best):
                    best = value
    return best


def _mysql_rows(connection, table, columns, wm_column, floor):
    cursor = connection.cursor()
    sql = f"SELECT {', '.join(columns)} FROM {table}"
    params = []
    if floor is not None:
        sql += f" WHERE {wm_column} > %s"
        params.append(floor)
    cursor.execute(sql + f" ORDER BY {next(iter(columns))}", params)
    try:
        while batch := cursor.fetchmany(BATCH_SIZE):
            yield from batch
    finally:
        cursor.close()


def _mongo_rows(database, collection, wm_index, floor):
    for document in database[collection].find({}).sort("_id", 1).batch_size(BATCH_SIZE):
        _, values = flatten_mongo(collection, document, None)
        row = values[:-2]
        if floor is None or row[wm_index] > floor:
            yield row


def _extract_entity(s3, bucket, source, entity, batch_id, columns, rows_for, force_full, workdir):
    wm_column = WATERMARK_COLUMN[(source, entity)]
    manifest_key = _prefix(source, entity, batch_id) + "_manifest.json"
    if _exists(s3, bucket, manifest_key):
        LOGGER.info("%s.%s lote %s ya extraído; no se sobrescribe", source, entity, batch_id)
        return json.loads(s3.get_object(Bucket=bucket, Key=manifest_key)["Body"].read()) | {"skipped": True}

    floor = None if force_full else _previous_watermark(s3, bucket, source, entity)
    wm_index = list(columns).index(wm_column)
    extracted_at = datetime.now(timezone.utc).replace(microsecond=0)
    seen = {"max": floor}

    def stamped():
        for row in rows_for(floor):
            value = row[wm_index]
            if value is not None and (seen["max"] is None or value > seen["max"]):
                seen["max"] = value
            yield (*row, batch_id, extracted_at.isoformat(sep=" "))

    data_name = f"{entity}.csv"
    path = Path(workdir) / source / data_name.replace(".csv", f"_{batch_id}.csv")
    headers = [*columns, "_batch_id", "_extracted_at"]
    count = _write_csv(path, headers, stamped())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    data_key = _prefix(source, entity, batch_id) + data_name
    s3.upload_file(str(path), bucket, data_key)
    manifest = {
        "source": source,
        "entity": entity,
        "batch_id": batch_id,
        "mode": "initial" if floor is None else "incremental",
        "extracted_at": extracted_at.isoformat(),
        "rows": count,
        "data_file": data_key,
        "sha256": digest,
        "columns": headers,
        "watermark_column": wm_column,
        "watermark_from": _dump(floor),
        "watermark_to": _dump(seen["max"]),
    }
    # El manifiesto va al final: su existencia significa "lote completo".
    s3.put_object(Bucket=bucket, Key=manifest_key, Body=json.dumps(manifest, indent=2).encode(), ContentType="application/json")
    LOGGER.info("%s.%s lote %s: %s filas (%s)", source, entity, batch_id, count, manifest["mode"])
    return manifest


def extract_to_s3(batch_id, bucket, force_full=False):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", batch_id):
        raise ValueError("batch_id solo admite letras, números, _ y -")
    s3 = boto3.client("s3")
    results = []
    with tempfile.TemporaryDirectory() as workdir:
        connection = connect_mysql()
        try:
            for table, columns in MYSQL_CSV_COLUMNS.items():
                wm = WATERMARK_COLUMN[("mysql", table)]
                results.append(_extract_entity(
                    s3, bucket, "mysql", table, batch_id, columns,
                    lambda floor, t=table, c=columns, w=wm: _mysql_rows(connection, t, c, w, floor),
                    force_full, workdir))
        finally:
            connection.close()
        client = MongoClient(os.environ["MONGODB_URI"], tz_aware=True)
        try:
            database = client[os.getenv("MONGO_DATABASE", "ecommerce")]
            for collection, columns in MONGO_CSV_COLUMNS.items():
                idx = list(columns).index(WATERMARK_COLUMN[("mongo", collection)])
                results.append(_extract_entity(
                    s3, bucket, "mongo", collection, batch_id, columns,
                    lambda floor, c=collection, i=idx: _mongo_rows(database, c, i, floor),
                    force_full, workdir))
        finally:
            client.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch-id", required=True, help="p. ej. 000 para la inicial, 001, 002...")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET"))
    parser.add_argument("--full", action="store_true", help="ignorar la marca de avance y extraer todo")
    args = parser.parse_args()
    if not args.bucket:
        sys.exit("Falta --bucket o la variable S3_BUCKET")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"{'fuente.entidad':32}{'modo':13}{'filas':>7}  hasta")
    for m in extract_to_s3(args.batch_id, args.bucket, args.full):
        mode = "(ya existía)" if m.get("skipped") else m["mode"]
        print(f"{m['source'] + '.' + m['entity']:32}{mode:13}{m['rows']:>7}  {m['watermark_to']}")


if __name__ == "__main__":
    main()
