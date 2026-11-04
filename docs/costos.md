# Estimación de costos (us-east-2, valores aproximados)

Precios de lista aproximados; confírmalos en la calculadora de AWS antes de citarlos como definitivos.

| Servicio | Configuración | Costo aproximado |
|---|---|---|
| EC2 | t3.medium | ~0,042 USD/hora |
| IP pública de la EC2 | 1 IPv4 | ~0,005 USD/hora |
| EBS | gp3 30 GB | ~2,4 USD/mes |
| RDS MySQL | db.t3.micro, 20 GB | ~0,017 USD/hora + ~2 USD/mes de disco |
| DocumentDB | 1 × db.t3.medium | ~0,078 USD/hora + almacenamiento y E/S |
| Redshift Serverless | 8 RPU base | ~0,375 USD por RPU-hora = ~3 USD/hora **solo mientras ejecuta consultas**; sin cobro de cómputo en reposo; almacenamiento ~0,024 USD/GB-mes |
| S3 | Pocos MB | Centavos |
| Secrets Manager | 2 secretos | ~0,40 USD/mes cada uno (prorrateado) |

## Escenarios
- **Siempre encendido (sin Redshift):** ~0,14 USD/hora, es decir ~100 USD/mes. Por eso la infraestructura no se deja corriendo.
- **Una sesión de trabajo (~4 h, con ~20 min de Redshift activo):** del orden de **1,5 a 2 USD**.
- **Después de `terraform destroy`:** 0 USD (verificado con consultas de la CLI filtradas por `dw-user10`, todas `[]`).

## Cómo se controló el gasto
- Cada servicio de pago tiene su bandera `enable_*` (por defecto `false`).
- Tamaños mínimos: `db.t3.micro`, `db.t3.medium` (el mínimo de DocumentDB), 8 RPU (el mínimo de Redshift Serverless).
- Sin Multi-AZ, sin snapshots finales, `force_destroy` en el bucket.
- Todo se creó y destruyó con Terraform, con verificación posterior.
