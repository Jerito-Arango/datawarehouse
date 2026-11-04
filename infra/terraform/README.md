# Infraestructura en AWS (Terraform)

Crea, en la región `us-east-2`, todo lo que necesita el Data Warehouse:

| Archivo | Recursos |
|---|---|
| `network.tf` | Sin recursos propios: toma la VPC por defecto de la cuenta y sus subredes |
| `security.tf` | Tres grupos de seguridad: `ec2` (SSH 22 y Airflow 8080 solo desde `my_ip`), `databases` (MySQL 3306 y DocumentDB 27017 solo desde el grupo de la EC2) y `redshift` (5439 solo desde la EC2) |
| `s3.tf` | Bucket privado, versionado y cifrado (`force_destroy`: `destroy` borra también su contenido) |
| `iam.tf` | Rol de Redshift para leer el bucket y rol/perfil de la EC2 |
| `rds.tf` | MySQL (RDS) con contraseña administrada en Secrets Manager |
| `docdb.tf` | DocumentDB (compatible con MongoDB) |
| `redshift.tf` | Redshift Serverless: namespace (con el rol de S3 asociado) y workgroup |
| `ec2.tf` | Llave SSH y EC2 `t3.medium` (Amazon Linux 2023, disco gp3 de 30 GB cifrado, IMDSv2 obligatorio): único punto de entrada a las bases de datos; ejecuta extracción, dbt y Airflow |
| `outputs.tf` | Endpoints, ARN del rol y de los secretos, IP de la EC2 |

## Variables

| Variable | Obligatoria | Descripción |
|---|---|---|
| `my_ip` | Sí | Tu IP pública con `/32`. Averíguala con `curl -s https://checkip.amazonaws.com` |
| `docdb_password` | Sí | Contraseña de DocumentDB. Va por entorno: `export TF_VAR_docdb_password='...'` (mínimo 8 caracteres). No se escribe en ningún archivo |
| `enable_rds`, `enable_docdb`, `enable_redshift`, `enable_ec2` | No (por defecto `false`) | Interruptores por servicio. Para el despliegue completo van en `true` (`terraform.tfvars.example`) |
| `project`, `owner`, `region` | No | Prefijo de nombres (`dw-user10`), etiqueta de dueño y región |
| `ssh_public_key_path` | No | Llave pública SSH para la EC2 (por defecto `~/.ssh/dw-user10.pub`) |
| `redshift_base_capacity` | No | RPU base de Redshift Serverless (por defecto 8, el mínimo) |

## Uso

```bash
ssh-keygen -t ed25519 -f ~/.ssh/dw-user10 -N ""      # una sola vez
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars          # edita my_ip; este archivo no se sube a Git
export TF_VAR_docdb_password='una-contraseña-segura'
terraform init
terraform plan
terraform apply
```

Los pasos posteriores (variables de entorno, EC2, carga de datos, pipeline) están en `docs/despliegue.md`.

Para destruir todo y dejar de pagar: `terraform destroy` desde esta carpeta, con `TF_VAR_docdb_password` definida. Borra también el bucket y los datos.

## Notas
- El estado (`terraform.tfstate`) es local y no se sube a Git (`.gitignore`).
- Las contraseñas de MySQL y Redshift las genera AWS y quedan en Secrets Manager; Terraform solo publica el ARN.
