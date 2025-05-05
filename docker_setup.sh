#!/usr/bin/env bash
# Script d'installation et de configuration de Cléa-API
# Compatible avec openSUSE Tumbleweed sous WSL et environnement Docker

set -e  # Arrêt en cas d'erreur

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Fonction d'affichage de messages
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCÈS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[ATTENTION]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERREUR]${NC} $1"
}

# Fonction pour précharger les modèles en mode Docker
docker_preload_models() {
    log "Mode Docker: Préchargement des modèles uniquement..."
    
    # Précharger le modèle CamemBERT
    log "Préchargement du modèle CamemBERT..."
    python -c "
from transformers import CamembertTokenizer, CamembertModel
print('Préchargement du modèle CamemBERT...')
tokenizer = CamembertTokenizer.from_pretrained('camembert-base')
model = CamembertModel.from_pretrained('camembert-base')
print('CamemBERT chargé avec succès')
"
    
    # Précharger les modèles Cross-Encoder
    log "Préchargement des modèles Cross-Encoder..."
    python -c "
from sentence_transformers import CrossEncoder
print('Préchargement des modèles Cross-Encoder...')
# Charger les modèles couramment utilisés
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('Cross-Encoder ms-marco-MiniLM-L-6-v2 chargé')
cross_encoder = CrossEncoder('cross-encoder/stsb-roberta-base')
print('Cross-Encoder stsb-roberta-base chargé')
print('Cross-Encoders chargés avec succès')
"
    
# Précharger le modèle Qwen si le fichier model_loader.py existe
    if [ -f "/app/temp_files/model_loader.py" ]; then
        log "Préchargement du modèle Qwen3-0.6B..."
        python -c "
import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

print('Préchargement du modèle Qwen3-0.6B...')
model_path = 'Qwen/Qwen3-0.6B'
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Vérifier si CUDA est disponible
if torch.cuda.is_available():
    print('CUDA détecté, chargement avec support GPU')
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map='auto'
    )
else:
    print('CUDA non détecté, chargement en mode CPU uniquement')
    # Chargement du modèle en mode CPU sans quantification
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float32,
        device_map='cpu',
        low_cpu_mem_usage=True
    )

print('Qwen3-0.6B chargé avec succès')
"
    else
        log_warning "model_loader.py non trouvé, modèle Qwen non préchargé"
    fi
    
    log_success "Modèles préchargés avec succès en mode Docker."
}

# Fonction principale
main() {
    # Vérifier si on est en mode Docker
    if [ "$1" = "--docker-mode" ]; then
        docker_preload_models
        return
    fi
    
    # Le reste du script original...
    echo -e "${BOLD}${BLUE}====== Installation de Cléa-API ======${NC}"
    
    # Vérifier la distribution
    check_distro
    
    # Installer les dépendances système
    install_system_dependencies
    
    # Configurer PostgreSQL
    setup_postgresql
    
    # Configurer l'utilisateur PostgreSQL
    setup_postgresql_user
    
    # Installer pgvector
    install_pgvector
    
    # Installer UV
    install_uv
    
    # Configurer l'environnement Python
    setup_python_env
    
    # Initialiser la base de données
    init_database
    
    # Précharger les modèles
    preload_models
    
    echo -e "${BOLD}${GREEN}====== Installation terminée avec succès ! ======${NC}"
    echo -e "${BOLD}Vous pouvez maintenant démarrer Cléa-API avec :${NC}"
    echo -e "  ${BLUE}./start.sh${NC}    OU    ${BLUE}uv run main.py${NC}"
}

# Exécuter la fonction principale avec tous les arguments
main "$@"