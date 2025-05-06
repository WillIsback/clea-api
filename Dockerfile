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
    
    # Ajouter l'utilisateur non-root
    RUN groupadd -r cleauser && useradd -r -g cleauser cleauser
    
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