# Controles de seguridad

## Red
- **Bases de datos y Redshift privadas:** `publicly_accessible = false` en RDS y Redshift; DocumentDB solo existe dentro de la VPC.
- **Grupos de seguridad con mínimo acceso:**
  - `ec2`: SSH (22) y Airflow (8080) solo desde `my_ip`.
  - `databases`: MySQL (3306) y DocumentDB (27017) solo desde el grupo de la EC2.
  - `redshift`: 5439 solo desde el grupo de la EC2.
- La EC2 es el único punto de entrada a los datos.

## Credenciales
- **RDS y Redshift:** `manage_master_user_password` / `manage_admin_password`: las contraseñas las genera y guarda AWS Secrets Manager; no existen en el código ni en el estado de Terraform.
- **DocumentDB:** la contraseña va por `TF_VAR_docdb_password`, nunca en un archivo; `.env.aws` solo tiene nombres y ARNs, y `aws_env.sh` pide o consulta las contraseñas en tiempo de ejecución.
- `.gitignore` excluye `.env.aws`, `terraform.tfvars`, estado y `.terraform/`. 

## IAM (mínimo privilegio)
- **Rol de Redshift:** solo `s3:GetObject` sobre el bucket del proyecto, más `ListBucket` y `GetBucketLocation`.
- **Rol de la EC2:** `GetObject`/`PutObject`/`ListBucket` solo sobre el bucket del proyecto y `GetSecretValue` solo sobre los dos secretos del proyecto. Sin credenciales de larga duración en la máquina.

## Datos
- **S3:** acceso público bloqueado (4 opciones), versionado, cifrado AES256.
- **Cifrado en reposo:** RDS (`storage_encrypted`), DocumentDB (`storage_encrypted`), disco de la EC2 (gp3 cifrado); Redshift Serverless cifra por defecto.
- **En tránsito:** DocumentDB con TLS y `global-bundle.pem`.
- **EC2:** IMDSv2 obligatorio.

## Limitaciones conocidas (aceptadas por ser un entorno de curso)
- La interfaz de Airflow va por HTTP, limitada a `my_ip`. En producción iría detrás de HTTPS/VPN.
- La EC2 tiene salida a internet abierta (necesaria para instalar paquetes).
- La contraseña de DocumentDB queda en el estado local de Terraform (`master_password`); por eso el estado no se versiona. En producción: estado remoto cifrado o contraseña gestionada.
- Airflow usa SQLite y `SequentialExecutor`: suficiente para una demo, no para producción.
- Las bases usan la VPC por defecto y todas las subredes (sin subredes privadas dedicadas).
- Sin Multi-AZ, con retención de backups de 1 día y `skip_final_snapshot` para poder destruir sin dejar costos.
