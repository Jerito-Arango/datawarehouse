# Documentación

## Entregables de la migración a AWS (este proyecto)
| Documento | Contenido |
|---|---|
| [despliegue.md](despliegue.md) | Cómo desplegar, ejecutar y destruir, paso a paso |
| [arquitectura.md](arquitectura.md) | Diagrama de arquitectura y flujo de un lote |
| [decisiones.md](decisiones.md) | Decisiones técnicas y diferencias frente al pipeline local |
| [seguridad.md](seguridad.md) | Controles de seguridad y limitaciones |
| [costos.md](costos.md) | Estimación de costos |
| [airflow_aws.md](airflow_aws.md) | DAG en AWS, marcadores de lote y demo de fallo |
| [cambios_redshift.md](cambios_redshift.md) | Cambios de dialecto para Redshift |

Infraestructura: [`infra/terraform/README.md`](../infra/terraform/README.md)

## Documentación original del pipeline local (profesor)
`architecture.md`, `airflow.md`, `connections.md`, `data_model.md`, `analytical_queries.sql` y la carpeta `etapas/` describen la versión local con DuckDB. Se conservan como referencia.
