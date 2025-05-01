#!/bin/bash
# Script d'installation pour Cléa-API sur OpenSUSE Tumbleweed (WSL)

set -e  # Arrêter en cas d'erreur

echo "=== Installation de Cléa-API sur OpenSUSE Tumbleweed (WSL) ==="
echo "Mise à jour du système..."
zypper -n ref
zypper -n up

echo "Installation des dépendances systèmes..."
zypper -n in postgresql-server postgresql-contrib postgresql-devel \
  python311 python311-devel python311-pip \
  gcc libopenssl-devel libffi-devel \
  git curl wget

echo "Installation de uv..."
curl -sSf https://astral.sh/uv/install.sh | sh

echo "Configuration de PostgreSQL..."
if [ ! -d "/var/lib/pgsql/data" ]; then
  echo "Initialisation du cluster PostgreSQL..."
  /usr/bin/postgresql-init
fi

echo "Démarrage du service PostgreSQL..."
systemctl enable postgresql
systemctl start postgresql

echo "Installation de pgvector..."
zypper -n in postgresql-server-devel
git clone --depth 1 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install
cd ..
rm -rf pgvector

echo "Configuration de la base de données..."
sudo -u postgres psql -c "CREATE DATABASE clea_db;"
sudo -u postgres psql -c "CREATE USER clea_user WITH ENCRYPTED PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE clea_db TO clea_user;"
sudo -u postgres psql -d clea_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "Installation des dépendances Python avec uv..."
cd /home/william/projet/Clea/clea-api
uv pip install -r requirements.txt

echo "Création du fichier .env..."
cat > .env << EOF
DB_USER=clea_user
DB_PASSWORD=your_password
DB_NAME=clea_db
DB_HOST=localhost
DB_PORT=5432
API_HOST=localhost
API_PORT=8080
EOF

echo "=== Installation terminée ==="
echo "Pour démarrer l'API, exécutez: ./start.sh"