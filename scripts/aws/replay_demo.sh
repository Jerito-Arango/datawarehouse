#!/usr/bin/env bash
# Repite el recorrido de la evidencia: lote inicial, lote incremental, y cambio SCD2 con un tercer lote.
# Uso, en la EC2 y desde ~/DE-DW, con el entorno cargado y las fuentes ya creadas (load_sources.sh):
#   source ~/venv/bin/activate && source scripts/aws/aws_env.sh && bash scripts/aws/replay_demo.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${S3_BUCKET:?Falta S3_BUCKET: ejecuta antes 'source scripts/aws/aws_env.sh'}"
DBT="$HOME/dbt-venv/bin/dbt"

ingest() {  # extrae a S3 y carga a Redshift el lote $1
  python -m ecommerce_dw.ingestion.s3_extract --batch-id "$1" --bucket "$S3_BUCKET"
  python -m ecommerce_dw.ingestion.redshift_load --batch-id "$1"
}
build() { (cd src/dbt && "$DBT" build); }
counts() {
  python scripts/aws/sql.py "select 'fct_sales', count(*) from marts.fct_sales union all select 'dim_customer', count(*) from marts.dim_customer"
}

(cd src/dbt && "$DBT" deps)
echo "== Lote 000: carga inicial =="; ingest 000; build; counts
echo "== Lote 001: incremental =="; python -m ecommerce_dw.sources.append_batch --batch-id 1; ingest 001; build; counts
echo "== Lote 002: cambio SCD2 + datos nuevos =="
python -m ecommerce_dw.sources.simulate_changes --customer-id 1 --product-id 1 --changed-at "$(date +%F)"
python -m ecommerce_dw.sources.append_batch --batch-id 2
ingest 002; build; counts
python scripts/aws/sql.py "select customer_id, city, valid_from, valid_to, is_current from marts.dim_customer where customer_id = 1 order by valid_from"
echo "Recorrido completo."
