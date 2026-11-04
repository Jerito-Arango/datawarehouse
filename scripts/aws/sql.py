"""Ejecuta una consulta en Redshift e imprime las filas. Uso: python scripts/aws/sql.py "select count(*) from marts.fct_sales"
Usa las variables REDSHIFT_* que carga scripts/aws/aws_env.sh."""

import os
import sys

import redshift_connector

connection = redshift_connector.connect(
    host=os.environ["REDSHIFT_HOST"],
    port=int(os.environ.get("REDSHIFT_PORT", 5439)),
    database=os.environ["REDSHIFT_DB"],
    user=os.environ["REDSHIFT_USER"],
    password=os.environ["REDSHIFT_PASSWORD"],
)
cursor = connection.cursor()
cursor.execute(sys.argv[1])
for row in cursor.fetchall():
    print(row)
connection.close()
