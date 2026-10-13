#!/bin/bash
# Crée un compte administrateur MariaDB pour phpMyAdmin (le compte root
# ne peut se connecter qu'avec sudo). Le mot de passe est demandé au clavier
# et n'est enregistré nulle part.
# Usage : bash database/create-admin.sh
set -e
read -rp  "Nom du compte administrateur : " ADMIN
read -rsp "Mot de passe (invisible)     : " PASS1; echo
read -rsp "Confirmer le mot de passe    : " PASS2; echo
[ "$PASS1" = "$PASS2" ] || { echo "Les mots de passe ne correspondent pas."; exit 1; }
[ ${#PASS1} -ge 10 ] || { echo "Choisir au moins 10 caractères."; exit 1; }

sudo mysql -u root <<SQL
CREATE USER IF NOT EXISTS '$ADMIN'@'localhost' IDENTIFIED BY '$PASS1';
ALTER USER '$ADMIN'@'localhost' IDENTIFIED BY '$PASS1';
GRANT ALL PRIVILEGES ON *.* TO '$ADMIN'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
SQL
echo "Compte $ADMIN prêt : connexion sur http://<IP_DU_PI>/phpmyadmin"
