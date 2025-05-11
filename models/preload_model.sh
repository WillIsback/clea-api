#!/bin/bash

#--------------------------------------------------
# Cléa-API - Script de préchargement des modèles
#
# Ce script télécharge les modèles nécessaires pour Cléa-API:
# - Modèle d'embeddings: almanach/camembertav2-base
# - Modèle de reranking: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
# - Modèle LLM: Qwen/Qwen3-0.6B
#--------------------------------------------------

set -e  # Arrêt du script en cas d'erreur

# Couleurs pour les logs
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Répertoires de destination
ROOT_DIR=$(dirname "$(dirname "$(readlink -f "$0")")")
MODELS_DIR="$ROOT_DIR/models"
EMBEDDINGS_DIR="$MODELS_DIR/embeddings"
RERANKING_DIR="$MODELS_DIR/reranking"
LLM_DIR="$MODELS_DIR/llm"

mkdir -p "$EMBEDDINGS_DIR" "$RERANKING_DIR" "$LLM_DIR"

# Configuration des modèles
declare -A MODELS
MODELS["embeddings"]="almanach/camembertav2-base"
MODELS["reranking"]="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MODELS["llm"]="Qwen/Qwen3-0.6B"

# Fonction de log
log() {
    echo -e "${CYAN}[$(date +"%Y-%m-%d %H:%M:%S")]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCÈS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[ATTENTION]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERREUR]${NC} $1" >&2
}

# Vérification des prérequis
check_prerequisites() {
    log "Vérification des prérequis..."
    
    # Vérifier si git est installé
    if ! command -v git &> /dev/null; then
        log_error "git n'est pas installé. Veuillez l'installer avec:"
        log_error "sudo zypper install git"
        exit 1
    fi
    
    # Vérifier si git-lfs est installé
    if ! command -v git-lfs &> /dev/null; then
        log_error "git-lfs n'est pas installé. Veuillez l'installer avec:"
        log_error "sudo zypper install git-lfs"
        exit 1
    fi
    
    # S'assurer que git-lfs est initialisé
    git lfs install > /dev/null
    
    log_success "Tous les prérequis sont satisfaits."
}

# Fonction pour créer les répertoires nécessaires
create_directories() {
    log "Création des répertoires pour les modèles..."
    mkdir -p "$EMBEDDINGS_DIR" "$RERANKING_DIR" "$LLM_DIR"
    log_success "Répertoires créés."
}

# Fonction pour télécharger un modèle spécifique
download_model() {
    local model_type=$1
    local model_name=${MODELS[$model_type]}
    local target_dir
    
    case $model_type in
        "embeddings") target_dir="$EMBEDDINGS_DIR" ;;
        "reranking") target_dir="$RERANKING_DIR" ;;
        "llm") target_dir="$LLM_DIR" ;;
        *) 
            log_error "Type de modèle inconnu: $model_type"
            return 1
            ;;
    esac
    
    local model_dir_name=$(basename "$model_name")
    local full_path="$target_dir/$model_dir_name"
    
    if [ -d "$full_path" ]; then
        log_warning "Le modèle $model_name existe déjà dans $full_path"
        read -p "Souhaitez-vous le télécharger à nouveau? (o/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Oo]$ ]]; then
            log "Téléchargement ignoré pour $model_name."
            return 0
        fi
        
        # Supprimer l'ancien dossier
        log "Suppression de l'ancienne version..."
        rm -rf "$full_path"
    fi
    
    log "Téléchargement du modèle $model_name vers $full_path..."
    
    # Cloner le dépôt avec Git LFS
    cd "$target_dir" || exit 1
    
    # Pour éviter les problèmes de profondeur de clone avec LFS
    GIT_LFS_SKIP_SMUDGE=1 git clone "https://huggingface.co/$model_name" "$model_dir_name"
    
    cd "$model_dir_name" || exit 1
    
    # Pull les fichiers LFS
    log "Téléchargement des fichiers binaires avec git-lfs..."
    git lfs pull
    
    log_success "Modèle $model_name téléchargé avec succès."
}

# Fonction pour télécharger tous les modèles
download_all_models() {
    log "Début du téléchargement de tous les modèles..."
    
    download_model "embeddings"
    download_model "reranking"
    download_model "llm"
    
    log_success "Tous les modèles ont été téléchargés avec succès."
}

# Fonction pour afficher l'aide
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --help              Affiche cette aide"
    echo "  --all               Télécharge tous les modèles"
    echo "  --embeddings        Télécharge uniquement le modèle d'embeddings"
    echo "  --reranking         Télécharge uniquement le modèle de reranking"
    echo "  --llm               Télécharge uniquement le modèle LLM"
    echo ""
    echo "Exemple:"
    echo "  $0 --all            Télécharge tous les modèles"
    echo "  $0 --embeddings     Télécharge uniquement le modèle d'embeddings"
}

# Fonction principale
main() {
    log "Démarrage du script de préchargement des modèles pour Cléa-API..."
    
    # Vérifier les prérequis
    check_prerequisites
    
    # Créer les répertoires
    create_directories
    
    # Gérer les options en ligne de commande
    if [ $# -eq 0 ]; then
        # Aucun argument fourni, télécharger tous les modèles
        download_all_models
    else
        case "$1" in
            --help)
                show_help
                ;;
            --all)
                download_all_models
                ;;
            --embeddings)
                download_model "embeddings"
                ;;
            --reranking)
                download_model "reranking"
                ;;
            --llm)
                download_model "llm"
                ;;
            *)
                log_error "Option non reconnue: $1"
                show_help
                exit 1
                ;;
        esac
    fi
    
    log_success "Préchargement des modèles terminé."
    log "Vous pouvez maintenant utiliser ces modèles avec Cléa-API en configurant les chemins dans votre fichier .env"
}

# Exécution de la fonction principale
main "$@"