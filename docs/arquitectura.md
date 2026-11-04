# Arquitectura

```mermaid
flowchart LR
  subgraph VPC["VPC por defecto (us-east-2)"]
    RDS[("RDS MySQL 8.0<br/>db.t3.micro, privado")]
    DOC[("DocumentDB<br/>db.t3.medium, privado")]
    EC2["EC2 t3.medium<br/>Airflow + extracción + dbt"]
    RS[("Redshift Serverless<br/>8 RPU base, privado")]
  end
  S3[("S3 raw/&lt;fuente&gt;/&lt;entidad&gt;/batch_id=N/<br/>+ _manifest.json")]
  SM["Secrets Manager<br/>contraseñas de RDS y Redshift"]
  ME(["Mi IP"])

  RDS -->|"1. extracción"| EC2
  DOC -->|"1. extracción (TLS)"| EC2
  EC2 -->|"2. CSV + manifest"| S3
  S3 -->|"3. COPY (rol IAM de Redshift)"| RS
  EC2 -->|"4. dbt: intermediate, snapshots, marts, tests"| RS
  SM -.->|"GetSecretValue"| EC2
  ME -->|"SSH 22 / Airflow 8080"| EC2
```

## Flujo de un lote (DAG `ecommerce_pipeline`)
`validate_environment` → `resolve_batch_id` → `extract_to_s3` → `load_to_redshift` → `dbt_deps` → `dbt_seed` → `dbt_run_intermediate` → `dbt_run_quarantine` → `dbt_snapshot` → `dbt_run_marts` → `dbt_test` → `reconcile_batch`

1. **Extracción:** lee MySQL (4 entidades) y DocumentDB (2 colecciones) desde la EC2 y escribe CSV en S3 bajo `raw/<fuente>/<entidad>/batch_id=<id>/`. El `_manifest.json` se escribe al final y marca el lote como completo.
2. **Carga:** `COPY` a `"raw".*` en Redshift, en una transacción por lote, y registro en `"raw".batch_control`.
3. **Transformación:** dbt crea intermediate (válidos y cuarentena), snapshots SCD2 y marts (dimensiones y `fct_sales`).
4. **Reconciliación:** verifica que lo cargado sea igual a válidos más cuarentena.

## Recursos de Terraform (22 con todo habilitado)
| Archivo | Recursos |
|---|---|
| `s3.tf` | Bucket (acceso público bloqueado, versionado, cifrado AES256) |
| `iam.tf` | Rol de Redshift (lee el bucket), rol y perfil de la EC2 (lee/escribe el bucket, lee dos secretos) |
| `rds.tf` | Subnet group e instancia MySQL |
| `docdb.tf` | Subnet group, clúster e instancia |
| `redshift.tf` | Namespace y workgroup |
| `security.tf`, `ec2.tf` | Tres grupos de seguridad, llave SSH, EC2 |
