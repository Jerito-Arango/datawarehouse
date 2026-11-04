# Decisiones técnicas y diferencias frente al pipeline local

| Tema | Local (profesor) | AWS (este proyecto) | Por qué |
|---|---|---|---|
| Almacén | DuckDB en archivo | Redshift Serverless | Servicio gestionado y sin servidores que administrar |
| Zona raw | Archivos locales / DuckDB | CSV en S3 `raw/<fuente>/<entidad>/batch_id=N/` + `_manifest.json` | S3 desacopla extracción y carga; el manifest es el marcador de lote completo |
| Carga | Lectura directa | `COPY` con rol IAM, una transacción por lote + `"raw".batch_control` | Idempotente: repetir un lote no duplica |
| Orquestación | Dos DAGs, DuckDB con bloqueo | Un DAG `ecommerce_pipeline` de 12 tareas | Un solo flujo completo con reintentos (2, espera exponencial) |
| MongoDB | Contenedor local | DocumentDB (TLS, `global-bundle.pem`, `replicaSet=rs0`, `retryWrites=false`) | Compatible con la API de Mongo, solo accesible dentro de la VPC |
| MySQL | Contenedor local | RDS MySQL con contraseña en Secrets Manager | Gestionado, cifrado |
| Infraestructura | Docker Compose | Terraform (22 recursos, banderas `enable_*`) | Reproducible, destruible, revisable |
| dbt | dbt-duckdb | dbt-redshift 1.9.5 sobre dbt-core 1.9.11 | Mismos modelos con ajustes de dialecto |
| Orquestador | Local | Airflow 2.11.2 en la misma EC2 (SQLite, `SequentialExecutor`) | Mínimo costo para la demo |

## Decisiones de diseño
- **Marcador de finalización:** el manifest se escribe al final. Un lote sin manifest no está completo y no se carga.
- **Marca de agua:** el máximo `watermark_to` de los manifests define dónde empieza el siguiente lote.
- **Reanudación:** `resolve_batch_id` abre un lote nuevo solo si el último está completo en S3 y cargado en Redshift (6 filas en `batch_control`); si no, lo reanuda. Así un reintento no crea lotes huérfanos.
- **Calidad:** registros inválidos van a cuarentena con su razón; `reconcile_batch` exige crudo = válidos + cuarentena.
- **Incrementales:** los hechos se recalculan con un `left join` contra la tabla destino (Redshift no admite subconsultas correlacionadas bajo `or`), más borrado de hechos huérfanos.
- **SCD2:** snapshots de dbt con estrategia `timestamp` sobre `updated_at`.

## Cambios de dialecto Redshift
Ver `docs/cambios_redshift.md` (palabra reservada `raw` entre comillas, `convert_timezone` con timestamp, etc.).

## Dashboard (requisito 3.6)
**No se implementó:** el profesor indicó que no se hiciera la parte de QuickSight.
