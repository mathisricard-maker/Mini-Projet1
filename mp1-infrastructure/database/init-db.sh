#!/bin/bash
# Crée la base, l'utilisateur de l'application et les tables.
# Les identifiants sont lus dans server/api/.env (à remplir AVANT de lancer ce script).
# Usage : bash database/init-db.sh       (relançable sans perte de données)
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DIR/../server/api/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Fichier $ENV_FILE introuvable."
  echo "Faire d'abord : cp server/api/.env.example server/api/.env  puis le remplir."
  exit 1
fi
set -a; . "$ENV_FILE"; set +a

for v in DB_USER DB_PASSWORD DB_NAME; do
  if [ -z "${!v}" ] || [[ "${!v}" == \<* ]]; then
    echo "La variable $v n'est pas remplie dans .env"; exit 1
  fi
done

echo "[1/4] Démarrage de MariaDB..."
sudo systemctl start mariadb

echo "[2/4] Création de la base $DB_NAME et de l'utilisateur..."
sudo mysql -u root <<SQL
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
ALTER USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
SQL

echo "[3/4] Import du schéma..."
MYSQL_PWD="$DB_PASSWORD" mysql -u "$DB_USER" "$DB_NAME" < "$DIR/schema.sql"

echo "[4/4] Tables présentes :"
MYSQL_PWD="$DB_PASSWORD" mysql -u "$DB_USER" "$DB_NAME" -e "SHOW TABLES;"
echo "Base de données prête."
