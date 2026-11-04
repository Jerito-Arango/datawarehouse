#!/usr/bin/env bash
# Deja listas las fuentes en AWS: esquema de MySQL (RDS), colecciones de DocumentDB y datos sintéticos.
# Reemplaza a create_source_schema.sh y generate_data.sh del proyecto original, que dependen de Docker.
# Uso, en la EC2 y desde ~/DE-DW, con el entorno cargado:
#   source ~/venv/bin/activate && source scripts/aws/aws_env.sh && bash scripts/aws/load_sources.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
for variable in MYSQL_HOST MYSQL_USER MYSQL_PASSWORD MYSQL_DATABASE MONGODB_URI; do
  [[ -n "${!variable:-}" ]] || { echo "Falta $variable: ejecuta antes 'source scripts/aws/aws_env.sh'" >&2; exit 1; }
done

echo "1/3 Esquema de MySQL..."
# MYSQL_PWD evita poner la contraseña en la línea de comandos. El esquema usa CREATE TABLE IF NOT EXISTS.
MYSQL_PWD="$MYSQL_PASSWORD" mysql -h "$MYSQL_HOST" -P "${MYSQL_PORT:-3306}" -u "$MYSQL_USER" "$MYSQL_DATABASE" \
  < src/ecommerce_dw/sources/mysql/schema.sql

echo "2/3 Colecciones de DocumentDB..."
python - <<'PY'
import os
from pymongo import MongoClient

database = MongoClient(os.environ["MONGODB_URI"])[os.environ.get("MONGO_DATABASE", "ecommerce")]
for name in ("reviews", "navigation_events"):
    if name not in database.list_collection_names():
        database.create_collection(name)
print("Colecciones listas:", sorted(database.list_collection_names()))
PY

echo "3/3 Datos sintéticos (valores por defecto: 50 clientes, 25 productos, 100 órdenes, semilla 42)..."
python -m ecommerce_dw.sources.generate_data
echo "Fuentes listas."
