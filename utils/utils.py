import logging
import os
from dotenv import load_dotenv
import pwd
import psycopg2
from sqlalchemy import inspect
import tomllib
from pathlib import Path
from typing import Optional

# Configuration du logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("clea-api")

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Variables de configuration PostgreSQL
POSTGRES_USER = os.getenv("DB_USER")
POSTGRES_PASSWORD = os.getenv("DB_PASSWORD")
POSTGRES_DB = os.getenv("DB_NAME")
POSTGRES_HOST = os.getenv("DB_HOST", "localhost")
POSTGRES_PORT = os.getenv("DB_PORT", "5432")


def get_current_user() -> str:
    """
    Obtient le nom de l'utilisateur actuel du shell.

    Returns:
        str: Nom de l'utilisateur actuel.
    """
    try:
        # Essayer plusieurs méthodes pour obtenir l'utilisateur
        # Méthode 1: via os.getlogin()
        try:
            return os.getlogin()
        except Exception:
            pass

        # Méthode 2: via les variables d'environnement
        if "USER" in os.environ:
            return os.environ["USER"]

        # Méthode 3: via l'UID
        return pwd.getpwuid(os.getuid())[0]
    except Exception as e:
        logger.warning(f"Impossible de déterminer l'utilisateur courant: {e}")
        return "unknown"


def check_postgres_status() -> bool:
    """
    Vérifie si le service PostgreSQL est en cours d'exécution.

    Returns:
        bool: True si PostgreSQL est en cours d'exécution, False sinon.
    """
    try:
        # Tenter une connexion simple pour vérifier que Postgres fonctionne
        conn = psycopg2.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


def verify_database_tables() -> bool:
    """Vérifie l'existence des tables nécessaires dans la base de données.

    Cette fonction se connecte à la base de données et vérifie l'existence
    des tables requises pour le fonctionnement de l'application.

    Returns:
        bool: True si toutes les tables requises existent, False sinon.
    """
    from vectordb.src.database import engine

    try:
        logger.info("Vérification des tables dans la base de données...")
        inspector = inspect(engine)
        required_tables = ["documents", "chunks", "index_configs"]
        existing_tables = inspector.get_table_names()

        logger.info(f"Tables existantes: {existing_tables}")

        for table in required_tables:
            if table not in existing_tables:
                logger.warning(f"❌ Table manquante: {table}")
                return False

        logger.info("✅ Toutes les tables requises existent.")
        return True

    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification des tables: {e}")
        return False


def get_version_from_pyproject() -> str:
    """Récupère la version du projet depuis pyproject.toml.
    
    Cette fonction lit la version définie dans le fichier pyproject.toml
    à la racine du projet.
    
    Returns:
        str: La version du projet ou "0.0.0" si non trouvée.
    """
    try:
        
        # Chemin absolu vers le répertoire racine du projet (parent de utils/)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pyproject_path = os.path.join(root_dir, "pyproject.toml")
        
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)
            return pyproject_data.get("project", {}).get("version", "0.0.0")
    except Exception as e:
        import logging
        logging.getLogger("root").warning(f"Erreur lors de la lecture de la version: {e}")
        return "0.0.0"


def get_logger(name: str) -> logging.Logger:
    """Récupère un logger avec le nom spécifié.

    Cette fonction allège la création des loggers en créant automatiquement
    des loggers hiérarchiques préfixés par l'application.

    Args:
        name: Nom du logger à créer (sans le préfixe 'clea-api').
            Par exemple: 'doc_loader.extractor' sera nommé 'clea-api.doc_loader.extractor'

    Returns:
        Instance de logger configurée selon les paramètres globaux.
    """
    # Préfixer tous les loggers avec 'clea-api' sauf si déjà présent
    if not name.startswith("clea-api"):
        if name:
            full_name = f"clea-api.{name}"
        else:
            full_name = "clea-api"
    else:
        full_name = name

    return logging.getLogger(full_name)
