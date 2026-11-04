# Despliegue, ejecución y destrucción

Todos los comandos se ejecutan desde la raíz del repositorio en tu computador, salvo los marcados como **EC2**.

## 0. Requisitos
- Terraform y AWS CLI instalados, con credenciales de la cuenta configuradas (`aws sts get-caller-identity` debe responder).
- Una llave SSH: `ssh-keygen -t ed25519 -f ~/.ssh/dw-user10 -N ""`.

## 1. Infraestructura
```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars      # edita my_ip
export TF_VAR_docdb_password='una-contraseña-segura'
terraform init && terraform apply
cd ../..
```
`apply` tarda varios minutos (DocumentDB y Redshift son los más lentos).

## 2. Variables de entorno y código en la EC2
```bash
scripts/aws/make_env.sh infra/terraform            # genera .env.aws (sin contraseñas, no se sube a Git)
scripts/aws/sync_to_ec2.sh                         # copia el repo a la EC2
IP=$(grep '^EC2_PUBLIC_IP=' .env.aws | cut -d= -f2)
ssh -i ~/.ssh/dw-user10 ec2-user@$IP 'bash -s' < scripts/aws/ec2_bootstrap.sh     # Python, librerías, dbt, certificado
ssh -i ~/.ssh/dw-user10 ec2-user@$IP 'bash -s' < scripts/aws/airflow_install.sh   # Airflow
```

## 3. Cargar las fuentes (EC2)
```bash
ssh -i ~/.ssh/dw-user10 ec2-user@$IP
cd ~/DE-DW
source ~/venv/bin/activate
source scripts/aws/aws_env.sh                      # pide la contraseña de DocumentDB
bash scripts/aws/load_sources.sh                   # esquema de MySQL, colecciones y datos sintéticos
```

## 4. Ejecutar el pipeline
**Opción A, a mano (EC2):**
```bash
python -m ecommerce_dw.ingestion.s3_extract --batch-id 000 --bucket $S3_BUCKET
python -m ecommerce_dw.ingestion.redshift_load --batch-id 000
cd src/dbt && ~/dbt-venv/bin/dbt deps && ~/dbt-venv/bin/dbt build
```
Para el recorrido completo de la evidencia (inicial, incremental y SCD2): `bash scripts/aws/replay_demo.sh`.

**Opción B, con Airflow (EC2):**
```bash
bash scripts/aws/airflow_start.sh                  # pide la contraseña de DocumentDB
cat ~/airflow/standalone_admin_password.txt
```
Abre `http://<ip-ec2>:8080` (usuario `admin`), y en el DAG `ecommerce_pipeline` pulsa **Trigger DAG**. Detalles, marca de lote y demostración de fallo en `docs/airflow_aws.md`.

Consultas a Redshift: `python scripts/aws/sql.py "select count(*) from marts.fct_sales"`.

## 5. Destruir
```bash
cd infra/terraform
export TF_VAR_docdb_password='cualquier-valor'     # Terraform la pide, aunque para destruir no importa cuál
terraform destroy
```
Verifica que no quede nada con el prefijo del proyecto:
```bash
aws docdb describe-db-clusters --region us-east-2 --query "DBClusters[?starts_with(DBClusterIdentifier,'dw-user10')].DBClusterIdentifier"
aws rds describe-db-instances --region us-east-2 --query "DBInstances[?starts_with(DBInstanceIdentifier,'dw-user10')].DBInstanceIdentifier"
aws redshift-serverless list-workgroups --region us-east-2 --query "workgroups[?starts_with(workgroupName,'dw-user10')].workgroupName"
aws ec2 describe-instances --region us-east-2 --filters "Name=tag:proyecto,Values=dw-user10" "Name=instance-state-name,Values=running,pending,stopping" --query "Reservations[].Instances[].InstanceId"
aws s3 ls | grep dw-user10
```
Todas deben devolver vacío. `destroy` borra el bucket con sus datos.
