#!/bin/bash
# Script de démarrage pour Cléa-API

set -e  # Arrêter en cas d'erreur

# Vérifier si PostgreSQL est en cours d'exécution
if ! systemctl is-active --quiet postgresql; then
    echo "Démarrage de PostgreSQL..."
    systemctl start postgresql
fi

# Vérifier si la création d'index est nécessaire
echo "Vérification de la configuration des index..."
uv python -c "from vectordb.src.database import check_and_update_indexes; check_and_update_indexes()"

# Démarrer l'API
echo "Démarrage de l'API..."
uv run uvicorn main:app --host $(grep API_HOST .env | cut -d '=' -f2) --port $(grep API_PORT .env | cut -d '=' -f2) --reload