"""
Point d'entrée principal de l'API Cléa.

Ce module configure et démarre l'application FastAPI avec uvicorn,
initialise la base de données et les index vectoriels, et gère
les erreurs globales de l'application.
"""

import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from vectordb.api.database_endpoint import router as database_router
from vectordb.api.index_endpoint import router as index_router
from vectordb.api.search_endpoint import router as search_router
from doc_loader.api.loader_endpoint import router as doc_loader_router
from pipeline.api.pipeline_endpoint import router as pipeline_router
from utils import (
    get_current_user,
    check_postgres_status,
    verify_database_tables,
    get_version_from_pyproject,
    get_logger,
)


# Configuration du logger
logger = get_logger("clea-api")

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Variables de configuration PostgreSQL
POSTGRES_USER = os.getenv("DB_USER")
POSTGRES_PASSWORD = os.getenv("DB_PASSWORD")
POSTGRES_DB = os.getenv("DB_NAME")
POSTGRES_HOST = os.getenv("DB_HOST", "localhost")
POSTGRES_PORT = os.getenv("DB_PORT", "5432")

# Variables de configuration API
API_HOST = os.getenv("API_HOST", "localhost")
API_PORT = int(os.getenv("API_PORT", 8080))
API_WORKERS = int(os.getenv("API_WORKERS", 1))
API_LOG_LEVEL = os.getenv("API_LOG_LEVEL", "info")
# Récupération de la version depuis pyproject.toml
VERSION = get_version_from_pyproject()
# Stockage des ressources globales
resources = {}


def start_postgres() -> bool:
    """
    Vérifie si PostgreSQL est disponible et suggère comment le démarrer si nécessaire.

    Cette fonction ne tente plus de démarrer automatiquement PostgreSQL via sudo,
    mais vérifie sa disponibilité et guide l'utilisateur si nécessaire.

    Returns:
        bool: True si PostgreSQL est accessible, False sinon.
    """
    current_user = get_current_user()
    logger.info(f"Utilisateur courant: {current_user}")

    # Vérifier si PostgreSQL est déjà en cours d'exécution
    if check_postgres_status():
        logger.info("PostgreSQL est déjà en cours d'exécution et accessible.")
        logger.info(
            f"Connexion établie à la base '{POSTGRES_DB}' sur {POSTGRES_HOST}:{POSTGRES_PORT}."
        )
        return True

    # PostgreSQL n'est pas en cours d'exécution ou pas accessible
    logger.warning("PostgreSQL n'est pas accessible avec la configuration actuelle.")
    logger.warning(
        f"Configuration: {POSTGRES_HOST}:{POSTGRES_PORT}, base '{POSTGRES_DB}', utilisateur '{POSTGRES_USER}'"
    )

    # Afficher des suggestions selon l'environnement
    import platform

    if platform.system() == "Linux":
        distro = ""
        try:
            # Tenter d'identifier la distribution Linux
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("ID="):
                        distro = line.split("=")[1].strip().strip('"')
                        break
        except Exception:
            pass

        if distro == "opensuse-tumbleweed":
            logger.info("Suggestions pour openSUSE Tumbleweed:")
            logger.info("1. Démarrer PostgreSQL: sudo systemctl start postgresql")
            logger.info(
                f"2. Vérifier si l'utilisateur {current_user} existe dans PostgreSQL:"
            )
            logger.info(f'   sudo -u postgres psql -c "\\du {current_user}"')
            logger.info(f"3. Si nécessaire, créer l'utilisateur {current_user}:")
            logger.info(f"   sudo -u postgres createuser --superuser {current_user}")
            logger.info(f"4. Créer la base {POSTGRES_DB} si elle n'existe pas:")
            logger.info(f"   sudo -u postgres createdb -O {current_user} {POSTGRES_DB}")
        else:
            logger.info("Pour démarrer PostgreSQL manuellement:")
            logger.info("1. sudo systemctl start postgresql")
            logger.info(
                f"2. Vérifier les permissions pour l'utilisateur {current_user}"
            )

    return False


def setup_database() -> bool:
    """Initialise la base de données et configure pgvector.

    Cette fonction crée les tables définies dans les modèles SQLAlchemy
    et configure l'extension pgvector pour les recherches vectorielles.

    Returns:
        bool: True si l'initialisation a réussi, False sinon.
    """
    logger.info("Initialisation de la base de données...")
    try:
        from vectordb.src.database import init_db, engine, Base

        # Créer toutes les tables définies dans Base
        Base.metadata.create_all(bind=engine)

        # Initialiser la base de données avec init_db
        init_db()

        # Configuration de pgvector
        with Session(engine) as session:
            try:
                session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.commit()
                logger.info("Extension pgvector installée avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de l'installation de pgvector: {e}")
                session.rollback()
                return False

        logger.info("✅ Base de données initialisée avec succès")
        return True

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire de cycle de vie de l'application.

    Initialise les ressources nécessaires au démarrage et les libère à l'arrêt.
    Vérifie et initialise la base de données et les index vectoriels.

    Args:
        app (FastAPI): Instance de l'application FastAPI.

    Yields:
        None: Contrôle rendu à l'application pendant son exécution.

    Raises:
        RuntimeError: Si la base de données ne peut pas être correctement initialisée.
    """
    logger.info("====== Démarrage de Cléa API ======")

    # Démarrer PostgreSQL si nécessaire
    if not resources.get("postgres_started"):
        if not start_postgres():
            logger.error("Échec du démarrage de PostgreSQL. Abandon.")
            raise RuntimeError("Échec du démarrage de PostgreSQL.")
        resources["postgres_started"] = True

    # Vérifier/initialiser les tables de la base de données
    if not verify_database_tables():
        logger.warning("Tables manquantes dans la base de données.")
        if not setup_database():
            logger.error("Échec de l'initialisation de la base de données.")
            raise RuntimeError("Échec de l'initialisation de la base de données.")

        # Vérifier à nouveau après initialisation
        if not verify_database_tables():
            logger.error("Les tables n'ont pas été créées correctement.")
            raise RuntimeError("Les tables n'ont pas été créées correctement.")

    logger.info("✅ Base de données et ressources initialisées avec succès")

    # Rendre le contrôle à l'application pendant son exécution
    yield

    # Nettoyage lors de l'arrêt
    logger.info("====== Arrêt de Cléa API ======")
    resources.clear()
    logger.info("✅ Ressources libérées")


# Création de l'application FastAPI avec le gestionnaire de cycle de vie
app = FastAPI(
    title="Cléa API",
    description="API pour gérer les documents et effectuer des recherches sémantiques.",
    version="VERSION",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    lifespan=lifespan,  # Gestionnaire de cycle de vie moderne
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routeurs
app.include_router(database_router, prefix="/database", tags=["Database"])
app.include_router(search_router, prefix="/search", tags=["Search"])
app.include_router(index_router, prefix="/index", tags=["Index"])
app.include_router(doc_loader_router, prefix="/doc_loader", tags=["DocLoader"])
app.include_router(pipeline_router, prefix="/pipeline", tags=["Pipeline"])


# Gestionnaires d'erreurs globaux
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    """Gestionnaire d'exceptions HTTP de Starlette.

    Args:
        request: Requête HTTP ayant provoqué l'exception.
        exc: Exception HTTP levée.

    Returns:
        JSONResponse: Réponse d'erreur formatée en JSON.
    """
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Gestionnaire d'erreurs de validation des requêtes.

    Args:
        request: Requête HTTP ayant provoqué l'exception.
        exc: Exception de validation levée.

    Returns:
        JSONResponse: Réponse d'erreur formatée en JSON avec détails.
    """
    return JSONResponse(
        {"error": "Invalid request", "details": exc.errors()}, status_code=422
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Gestionnaire d'exceptions global capturant toutes les erreurs non gérées.

    Args:
        request: Requête HTTP ayant provoqué l'exception.
        exc: Exception générale levée.

    Returns:
        JSONResponse: Réponse d'erreur formatée en JSON.
    """
    logger.exception("Exception non gérée")
    return JSONResponse(
        {"error": "Internal server error", "details": str(exc)}, status_code=500
    )


# Point de santé
@app.get("/")
async def root():
    """Endpoint racine pour vérifier l'état de l'API.

    Returns:
        dict: Message indiquant que l'API est en cours d'exécution.
    """
    return {"message": "Cléa API is running"}


# Point d'entrée principal
if __name__ == "__main__":
    # Configuration optimisée d'Uvicorn
    config = uvicorn.Config(
        app="main:app",
        host=API_HOST,
        port=API_PORT,
        log_level=API_LOG_LEVEL,
        reload=True,
        workers=API_WORKERS,
        loop="auto",  # Utiliser uvloop si disponible
        http="auto",  # Utiliser httptools si disponible
        ws="auto",
        proxy_headers=True,  # Important pour les déploiements derrière un proxy
        access_log=True,
    )

    # Démarrage du serveur
    server = uvicorn.Server(config)
    server.run()
