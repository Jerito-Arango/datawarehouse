# Cambios frente a la versión local (DuckDB → Redshift)

Estado: primera ejecución de `dbt build` en Redshift con 96 pruebas aprobadas y 3 errores de sintaxis, corregidos en esta versión.

## Carga (sección 3.3)
| Local (DuckDB) | AWS (Redshift) | Motivo |
|---|---|---|
| `raw_ingestion.py`: borra e inserta toda la tabla `raw` en cada corrida | `redshift_load.py`: `COPY` por lote desde S3, borrando antes solo las filas del mismo `_batch_id` | La extracción es incremental y por lote; repetir un lote no duplica |
| `raw` es una foto completa | `raw` acumula lotes (`_batch_id`, `_extracted_at`) | Conserva el historial y permite reprocesar |
| Sin control de lotes | `raw.batch_control` se escribe en la misma transacción que los datos | Un lote queda cargado completo o no queda |
| Columna `JSON` | `VARCHAR(65535)` | Los CSV se cargan con `COPY`; el JSON se consulta con `json_extract_path_text` |
| Esquema `raw` | `"raw"` entre comillas | `RAW` es palabra reservada en Redshift |

## dbt
| Archivo | Cambio |
|---|---|
| `profiles.yml` | Adaptador `redshift`; host, usuario y contraseña desde variables de entorno |
| `stg_*` (6) | Dejan la versión más reciente de cada llave (`row_number`) y propagan `_batch_id`; las filas sin llave pasan a calidad |
| `int_*__valid` (6) | `select * exclude (...)` no es portable: se listan las columnas |
| `stg_mongodb__reviews` | `json_extract_string` → `json_extract_path_text`; el `cast(texto as boolean)` no existe en Redshift y se reemplaza por un `case` |
| `fct_reviews`, `fct_navigation_events` y una prueba | `timezone(zona, ts)` → macro `to_business_time` (`convert_timezone` sobre un `timestamp`: no acepta `timestamptz`) |
| `dim_date` | `isodow` → macro `iso_dow` (en Redshift `dow` va de 0 a 6) |
| `macros/incremental.sql` y 3 pruebas | `is distinct from` → macro `is_distinct` |
| `assert_dim_date_covers_configured_range` | `datediff('day', ...)` → `datediff(day, ...)` |
| `sources.yml` | Esquema `raw` citado |
| `macros/incremental.sql` | `exists` correlacionado dentro de un `or` no lo admite Redshift → `left join` contra la tabla destino; se verificó que devuelve las mismas filas que el filtro original |
| Prueba nueva | `assert_bogota_conversion_is_utc_minus_5` verifica la conversión horaria con un valor conocido |

Sin cambios: reglas de calidad, capas, SCD2 (snapshots), llaves sustitutas, ventana de reproceso y pruebas de negocio.

## Límite conocido
La extracción incremental no detecta filas borradas en el origen. La versión local sí, porque recargaba todo.
