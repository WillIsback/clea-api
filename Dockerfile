# Étape de construction: installation des dépendances avec support CUDA
FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04 AS builder

# Installation des dépendances système et Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    pkg-config \
    cmake \
    git \
    curl \
    ca-certificates \
    protobuf-compiler \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    libblas-dev \
    liblapack-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

    
# Garantir que Python 3.11 est la version par défaut
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
&& update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Vérifier la version Python utilisée
RUN python --version && python3 --version

# Installation de uv pour respecter l'environnement habituel
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH"

# Configuration de l'environnement Python
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR=/opt/uv-cache/
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

# Copier les fichiers de dépendances
COPY pyproject.toml requirements.txt ./
COPY askai/requirements_askai.txt ./askai/

# Installation des dépendances avec support GPU
# 1. psycopg en premier pour garantir sa disponibilité
RUN --mount=type=cache,target=/opt/uv-cache/ \
    uv pip install --system --no-cache-dir "psycopg[binary]>=3.0.0"

# 2. Installation des dépendances principales sans openapi-markdown (pour éviter conflits)
RUN grep -v "openapi-markdown" requirements.txt > requirements_filtered.txt && \
    uv pip install --system --no-cache-dir -r requirements_filtered.txt && \
    uv pip install --system --no-cache-dir openapi-markdown==0.2.1 --no-deps && \
    uv pip install --system --no-cache-dir jinja2==3.1.4

# 3. Installation de PyTorch avec support CUDA
RUN --mount=type=cache,target=/opt/uv-cache/ \
    uv pip install --system --no-cache-dir torch torchvision torchaudio

# 4. Installation des dépendances de askai y compris packages NVIDIA
RUN --mount=type=cache,target=/opt/uv-cache/ \
    uv pip install --system --no-cache-dir -r askai/requirements_askai.txt

# 5. Installation de bitsandbytes avec support CUDA
RUN --mount=type=cache,target=/opt/uv-cache/ \
    uv pip install --system --no-cache-dir bitsandbytes

# Vérification de l'installation avec support CUDA
RUN python -c "import torch; print(f'PyTorch version: {torch.__version__}, CUDA available: {torch.cuda.is_available()}')" || echo "CUDA check skipped in build phase"

# Copier le code source de l'application
COPY . .

# Étape finale: image d'exécution légèrement plus légère
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04
# Installation de uv pour respecter l'environnement habituel
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Installation des dépendances runtime uniquement
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    libpq5 \
    netcat-openbsd \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Configuration de l'environnement
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

WORKDIR /app

# Copier les fichiers de l'application
COPY --from=builder /app/askai /app/askai
COPY --from=builder /app/vectordb /app/vectordb
COPY --from=builder /app/doc_loader /app/doc_loader
COPY --from=builder /app/pipeline /app/pipeline
COPY --from=builder /app/stats /app/stats
COPY --from=builder /app/utils /app/utils
COPY --from=builder /app/main.py /app/
COPY --from=builder /app/pyproject.toml /app/
COPY --from=builder /app/requirements.txt /app/

# Répertoire pour les modèles (montés comme volume)
RUN mkdir -p /app/models
RUN uv venv
RUN uv pip install psycopg[binary]>=3.0.0 APScheduler
RUN uv pip install -r requirements.txt
RUN apt-get update && apt-get install -y curl
RUN uv pip install --system --no-cache-dir accelerate
# Démarrer l'application avec uv
ENTRYPOINT ["uv", "run", "main.py"]