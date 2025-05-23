"""
Point d'entrée principal de l'API Cléa.

Ce module configure et démarre l'application FastAPI avec uvicorn,
initialise la base de données et les index vectoriels, et gère
les erreurs globales de l'application.
"""

import os
import sys
from contextlib import asynccontextmanager
import argparse
import logging
from typing import AsyncGenerator
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import PlainTextResponse
from vectordb.src.database import engine
from vectordb.api.database_endpoint import router as database_router
from vectordb.api.index_endpoint import router as index_router
from vectordb.api.search_endpoint import router as search_router
from doc_loader.api.loader_endpoint import router as doc_loader_router
from pipeline.api.pipeline_endpoint import router as pipeline_router
from askai.api.askai_endpoint import router as askai_router
from stats.api.stats_api_endpoint import router as stats_router

from vectordb.src.index_cleaner import schedule_cleanup_job

from utils import (
    get_current_user,
    check_postgres_status,
    verify_database_tables,
    get_version_from_pyproject,
    get_logger,
)


logger = get_logger("")

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
# Variable d'url Frontend pour CORS
FRONTEND_URLS = os.getenv("FRONTEND_URLS", "http://localhost").split(",")
# Détermine si toutes les origines sont autorisées
ALLOW_ALL_ORIGINS = os.getenv("ALLOW_ALL_ORIGINS", "false").lower() == "true"
# Récupération de la version depuis pyproject.toml
VERSION = get_version_from_pyproject()
# Stockage des ressources globales
resources = {}


# Configuration du logger
def configure_logging(debug_mode: bool = False) -> None:
    """Configure le système de journalisation global.

    Définit le niveau de journalisation pour toute l'application et ajuste
    les loggers externes pour une verbosité appropriée.

    Args:
        debug_mode: Si True, active les logs de niveau DEBUG dans toute l'application.
    """
    log_level = logging.DEBUG if debug_mode else logging.INFO

    # Configuration du logger racine - POINT CLÉ
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Logger principal de l'application
    app_logger = logging.getLogger("clea-api")

    # Réduire la verbosité des loggers tiers uniquement
    logging.getLogger("uvicorn").setLevel(
        logging.WARNING if not debug_mode else logging.INFO
    )
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING if not debug_mode else logging.INFO
    )
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if not debug_mode else logging.INFO
    )

    app_logger.info(
        f"Niveau de journalisation configuré: {logging.getLevelName(log_level)}"
    )


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
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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

    # Lancer le nettoyage des index orphelins
    if not resources.get("cleanup_job_started"):
        schedule_cleanup_job(interval_hours=24)
        resources["cleanup_job_started"] = True
        logger.info("✅ Job de nettoyage des index orphelins démarré")
    else:
        logger.info("Job de nettoyage des index orphelins déjà démarré")

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
    allow_origins=["*"] if ALLOW_ALL_ORIGINS else [FRONTEND_URLS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Inclusion des routeurs
app.include_router(database_router, prefix="/database", tags=["Database"])
app.include_router(search_router, prefix="/search", tags=["Search"])
app.include_router(index_router, prefix="/index", tags=["Index"])
app.include_router(doc_loader_router, prefix="/doc_loader", tags=["DocLoader"])
app.include_router(pipeline_router, prefix="/pipeline", tags=["Pipeline"])
app.include_router(askai_router, prefix="/askai", tags=["AskAI"])
app.include_router(stats_router, prefix="/stats", tags=["Stats"])


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

# Endpoint de santé dédié pour les healthchecks Docker
@app.get("/health", response_class=PlainTextResponse)
async def health_check():
    """Endpoint dédié aux healthchecks pour Docker.
    Vérifie la disponibilité de l'API et de la base de données.
    
    Returns:
        str: Message simple indiquant que l'API est opérationnelle.
    """
    try:
        # Vérification simplifiée de la connexion à la base de données
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "OK"
    except Exception as e:
        logger.error(f"Échec du healthcheck: {e}")
        raise StarletteHTTPException(status_code=503, detail="Service unavailable")
    
# Point d'entrée principal
if __name__ == "__main__":
    # Analyser les arguments en ligne de commande
    parser = argparse.ArgumentParser(description="Serveur Cléa-API")
    parser.add_argument(
        "--debug", action="store_true", help="Active le mode debug avec logs détaillés"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=API_PORT,
        help=f"Port du serveur (défaut: {API_PORT})",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=API_HOST,
        help=f"Hôte du serveur (défaut: {API_HOST})",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=API_WORKERS,
        help=f"Nombre de workers (défaut: {API_WORKERS})",
    )

    args = parser.parse_args()

    # Configurer la journalisation en fonction du mode debug
    configure_logging(debug_mode=args.debug)

    # Ajuster le niveau de log pour uvicorn
    uvicorn_log_level = "debug" if args.debug else API_LOG_LEVEL

    # Configuration optimisée d'Uvicorn
    config = uvicorn.Config(
        app="main:app",
        host=args.host,
        port=args.port,
        log_level=uvicorn_log_level,
        timeout_keep_alive=300,  # Augmenter ce timeout
        timeout_graceful_shutdown=300,  # Et celui-ci aussi
        limit_concurrency=5,  # Limiter la concurrence pour éviter les OOM
        reload=True,
        workers=args.workers,
        loop="auto",  # Utiliser uvloop si disponible
        http="auto",  # Utiliser httptools si disponible
        ws="auto",
        proxy_headers=True,  # Important pour les déploiements derrière un proxy
        access_log=args.debug,  # Logs d'accès uniquement en mode debug
    )

    logger.info(
        f"Démarrage du serveur Cléa-API sur {args.host}:{args.port} avec {args.workers} worker(s)"
    )

    # Démarrage du serveur
    server = uvicorn.Server(config)
    server.run()
