"""Carga de S3 a Redshift con COPY (sección 3.3).

- Lee el manifiesto de cada entidad del lote y copia su CSV a "raw"."<tabla>".
- raw acumula todos los lotes: cada fila lleva _batch_id y _extracted_at.
- Idempotente: antes de copiar borra las filas del mismo lote, así repetir un lote no duplica.
- Todo el lote va en UNA transacción. La marca de lote terminado ("raw".batch_control)
  se escribe dentro de esa transacción: o quedan las seis entidades y su marca, o nada.
- Redshift lee S3 con un rol IAM (REDSHIFT_ROLE_ARN, o el rol por defecto del namespace).
"""

import argparse
import json
import logging
import os
import sys

import boto3
import redshift_connector

LOGGER = logging.getLogger(__name__)

# (fuente, entidad) -> (tabla, etiqueta de _source, columnas de negocio). Los nombres y el orden
# deben coincidir con MYSQL_CSV_COLUMNS / MONGO_CSV_COLUMNS de s3_extract.py.
RAW_TABLES = {
    ("mysql", "customers"): ("mysql_customers", "mysql.customers",
        "customer_id BIGINT, name VARCHAR(1024), email VARCHAR(1024), phone VARCHAR(256), city VARCHAR(512), "
        "department VARCHAR(512), registration_date DATE, updated_at TIMESTAMP"),
    ("mysql", "products"): ("mysql_products", "mysql.products",
        "product_id BIGINT, name VARCHAR(1024), category VARCHAR(512), price DECIMAL(12,2), "
        "description VARCHAR(4096), is_active BOOLEAN, updated_at TIMESTAMP"),
    ("mysql", "orders"): ("mysql_orders", "mysql.orders",
        "order_id BIGINT, customer_id BIGINT, order_date TIMESTAMP, status VARCHAR(256), "
        "sales_channel VARCHAR(256), payment_method VARCHAR(256), total DECIMAL(14,2)"),
    ("mysql", "order_items"): ("mysql_order_items", "mysql.order_items",
        "order_item_id BIGINT, order_id BIGINT, product_id BIGINT, quantity INTEGER, "
        "unit_price DECIMAL(12,2), subtotal DECIMAL(14,2)"),
    ("mongo", "reviews"): ("mongo_reviews", "mongodb.reviews",
        "review_id BIGINT, customer_id BIGINT, product_id BIGINT, rating INTEGER, "
        "reviewed_at TIMESTAMPTZ, document_json VARCHAR(65535)"),
    ("mongo", "navigation_events"): ("mongo_navigation_events", "mongodb.navigation_events",
        "event_id BIGINT, event_type VARCHAR(256), occurred_at TIMESTAMPTZ, customer_id BIGINT, "
        "product_id BIGINT, sales_channel VARCHAR(256), document_json VARCHAR(65535)"),
}


def connect():
    user = os.getenv("REDSHIFT_USER", "dwadmin")
    password = os.getenv("REDSHIFT_PASSWORD")
    if not password and os.getenv("REDSHIFT_SECRET_ARN"):
        secret = json.loads(boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["REDSHIFT_SECRET_ARN"])["SecretString"])
        user, password = secret["username"], secret["password"]
    return redshift_connector.connect(
        host=os.environ["REDSHIFT_HOST"],
        port=int(os.getenv("REDSHIFT_PORT", "5439")),
        database=os.getenv("REDSHIFT_DB", "dw"),
        user=user,
        password=password,
    )


def create_objects(cursor):
    """Crea el esquema, las tablas raw y la tabla de control si no existen. 'raw' va entre comillas: es palabra reservada."""
    cursor.execute('CREATE SCHEMA IF NOT EXISTS "raw"')
    for table, label, columns in RAW_TABLES.values():
        cursor.execute(
            f'CREATE TABLE IF NOT EXISTS "raw".{table} ({columns}, '
            f"_batch_id VARCHAR(64), _extracted_at TIMESTAMPTZ, "
            f"_loaded_at TIMESTAMPTZ DEFAULT getdate(), _source VARCHAR(64) DEFAULT '{label}')"
        )
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS "raw".batch_control ('
        "source VARCHAR(32), entity VARCHAR(64), batch_id VARCHAR(64), rows_expected BIGINT, rows_loaded BIGINT, "
        "extracted_at TIMESTAMPTZ, loaded_at TIMESTAMPTZ DEFAULT getdate(), status VARCHAR(16))"
    )


def _manifest(s3, bucket, source, entity, batch_id):
    key = f"raw/{source}/{entity}/batch_id={batch_id}/_manifest.json"
    try:
        return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    except s3.exceptions.NoSuchKey:
        raise FileNotFoundError(f"No existe el manifiesto s3://{bucket}/{key}: extrae el lote antes de cargarlo") from None


def load_batch(batch_id, bucket):
    s3 = boto3.client("s3")
    role = os.getenv("REDSHIFT_ROLE_ARN")
    iam_role = f"IAM_ROLE '{role}'" if role else "IAM_ROLE DEFAULT"
    # Primero se leen todos los manifiestos: si falta alguno, no se toca Redshift.
    manifests = {key: _manifest(s3, bucket, *key, batch_id) for key in RAW_TABLES}
    connection = connect()
    cursor = connection.cursor()
    results = []
    try:
        create_objects(cursor)
        for (source, entity), (table, label, _) in RAW_TABLES.items():
            manifest = manifests[(source, entity)]
            columns = ", ".join(manifest["columns"])
            cursor.execute(f'DELETE FROM "raw".{table} WHERE _batch_id = %s', (batch_id,))
            cursor.execute(
                f"COPY \"raw\".{table} ({columns}) FROM 's3://{bucket}/{manifest['data_file']}' "
                f"{iam_role} FORMAT AS CSV IGNOREHEADER 1 TIMEFORMAT 'auto' DATEFORMAT 'auto'"
            )
            cursor.execute(f'SELECT COUNT(*) FROM "raw".{table} WHERE _batch_id = %s', (batch_id,))
            loaded = cursor.fetchone()[0]
            if loaded != manifest["rows"]:
                raise ValueError(f"{source}.{entity} lote {batch_id}: el manifiesto dice {manifest['rows']} filas y Redshift cargó {loaded}")
            cursor.execute('DELETE FROM "raw".batch_control WHERE source = %s AND entity = %s AND batch_id = %s',
                           (source, entity, batch_id))
            cursor.execute(
                'INSERT INTO "raw".batch_control (source, entity, batch_id, rows_expected, rows_loaded, extracted_at, status) '
                "VALUES (%s, %s, %s, %s, %s, %s, 'loaded')",
                (source, entity, batch_id, manifest["rows"], loaded, manifest["extracted_at"].replace("T", " ")),
            )
            results.append((source, entity, manifest["rows"], loaded))
            LOGGER.info("%s.%s lote %s: %s filas cargadas", source, entity, batch_id, loaded)
        connection.commit()  # la marca de lote y los datos se confirman juntos
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="Carga un lote de S3 a Redshift con COPY.")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET"))
    args = parser.parse_args()
    if not args.bucket:
        sys.exit("Falta --bucket o la variable S3_BUCKET")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"{'fuente.entidad':32}{'esperadas':>10}{'cargadas':>10}")
    for source, entity, expected, loaded in load_batch(args.batch_id, args.bucket):
        print(f"{source + '.' + entity:32}{expected:>10}{loaded:>10}")


if __name__ == "__main__":
    main()
