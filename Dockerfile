# --- STAGE 1: Build image ---
    FROM opensuse/tumbleweed:latest AS builder

    # Définition des variables d'environnement
    ENV PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1 \
        TZ=Europe/Paris \
        PATH="/root/.local/bin:$PATH"
    
    # Installation des dépendances système nécessaires
    RUN zypper --non-interactive refresh && \
        zypper --non-interactive install \
        curl \
        ca-certificates \
        gcc \
        git \
        make \
        python311 \
        python311-devel \
        python311-pip \
        && zypper clean -a
    
    # Installer UV (gestionnaire de paquets Python moderne)
    ADD https://astral.sh/uv/install.sh /uv-installer.sh
    RUN sh /uv-installer.sh && rm /uv-installer.sh
    
    # Créer un utilisateur non-root
    RUN groupadd -r cleauser && useradd -r -g cleauser cleauser
    
    # Créer et définir le répertoire de travail
    WORKDIR /app
    
    # Copier uniquement les fichiers de dépendances pour optimiser le cache Docker
    COPY requirements.txt ./
    COPY askai/requirements_askai.txt ./askai/
    
    # Installer les dépendances avec UV
    RUN uv venv /app/.venv
    ENV PATH="/app/.venv/bin:$PATH"
    RUN uv pip install --no-cache-dir -r requirements.txt -r askai/requirements_askai.txt
    
    # Précharger les modèles Hugging Face 
    RUN mkdir -p /app/models/hf_cache
    ENV HF_HOME=/app/models/hf_cache \
        TRANSFORMERS_CACHE=/app/models/hf_cache \
        SENTENCE_TRANSFORMERS_HOME=/app/models/hf_cache
    
    # Copier les fichiers nécessaires pour le préchargement des modèles
    COPY vectordb/src/ranking.py /app/temp_files/
    COPY vectordb/src/embeddings.py /app/temp_files/
    COPY askai/src/model_loader.py /app/temp_files/
    
    # Copier une version modifiée de setup.sh pour le préchargement des modèles
    COPY docker_setup.sh /app/docker_setup.sh
    RUN chmod +x /app/docker_setup.sh
    
    # Exécuter le préchargement des modèles via setup.sh
    # Note: On exécute uniquement la partie préchargement des modèles
    RUN /app/docker_setup.sh --docker-mode
    
    # --- STAGE 2: Runtime image ---
    FROM opensuse/tumbleweed:latest AS runtime
    
    # Installer les dépendances minimales nécessaires à l'exécution
    RUN zypper --non-interactive refresh && \
        zypper --non-interactive install \
        python311 \
        ca-certificates \
        && zypper clean -a
    
    # Copier l'environnement virtuel du builder
    COPY --from=builder /app/.venv /app/.venv
    
    # Copier le cache des modèles Hugging Face
    COPY --from=builder /app/models /app/models
    
    # Ajouter l'utilisateur non-root
    RUN groupadd -r cleauser && useradd -r -g cleauser cleauser
    
    # Définir les variables d'environnement
    ENV PATH="/app/.venv/bin:$PATH" \
        PYTHONUNBUFFERED=1 \
        PYTHONDONTWRITEBYTECODE=1 \
        TZ=Europe/Paris \
        HF_HOME="/app/models/hf_cache" \
        TRANSFORMERS_OFFLINE=1 \
        SENTENCE_TRANSFORMERS_HOME="/app/models/hf_cache"
    
    # Créer le répertoire de travail
    WORKDIR /app
    COPY . /app/
    
    # Donner la propriété de tous les fichiers à l'utilisateur non-root
    RUN chown -R cleauser:cleauser /app
    
    # Changer pour l'utilisateur non-root
    USER cleauser
    
    # Exposer le port par défaut
    EXPOSE 8080
    
    # Démarrer l'application
    ENTRYPOINT ["uvicorn"]
    CMD ["main:app", "--host", "0.0.0.0", "--port", "8080"]