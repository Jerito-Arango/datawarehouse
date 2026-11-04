# Carga el entorno completo en la sesión de la EC2. Se ejecuta con "source", no con "bash".
# Uso, desde ~/DE-DW:  source scripts/aws/aws_env.sh
# Lee .env.aws (sin secretos), pide la contraseña de DocumentDB y trae las demás desde Secrets Manager.
if [ ! -f .env.aws ]; then echo "Falta .env.aws: ejecuta scripts/aws/sync_to_ec2.sh desde tu computador"; return 1; fi
set -a; . ./.env.aws; set +a
export AWS_PAGER=""
read -r -s -p "Contraseña de DocumentDB: " DOCDB_PASSWORD; echo
export DOCDB_PASSWORD
_secret() { aws secretsmanager get-secret-value --secret-id "$1" --query SecretString --output text | python3 -c "import sys,json;print(json.load(sys.stdin)['$2'])"; }
export MYSQL_HOST="$RDS_ENDPOINT" MYSQL_PORT=3306 MYSQL_USER=admin MYSQL_DATABASE=source
export MYSQL_PASSWORD="$(_secret "$RDS_SECRET_ARN" password)"
_enc="$(python3 -c 'import os,urllib.parse as u;print(u.quote(os.environ["DOCDB_PASSWORD"],safe=""))')"
export MONGODB_URI="mongodb://docdbadmin:${_enc}@${DOCDB_ENDPOINT}:27017/?tls=true&tlsCAFile=$HOME/global-bundle.pem&replicaSet=rs0&retryWrites=false"
export MONGO_DATABASE=ecommerce
export REDSHIFT_HOST="$REDSHIFT_ENDPOINT" REDSHIFT_DB=dw REDSHIFT_USER=dwadmin
export REDSHIFT_PASSWORD="$(_secret "$REDSHIFT_SECRET_ARN" password)"
export PYTHONPATH="$PWD/src" DBT_PROFILES_DIR="$PWD/src/dbt"
unset -f _secret; unset _enc
echo "Entorno cargado. Longitudes (deben ser > 0): MySQL=${#MYSQL_PASSWORD} DocumentDB=${#DOCDB_PASSWORD} Redshift=${#REDSHIFT_PASSWORD}"
