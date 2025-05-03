import logging
import os
from dotenv import load_dotenv
import pwd
import psycopg2
from sqlalchemy import inspect
import tomllib
from pathlib import Path

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
    """Récupère la version du projet depuis le fichier pyproject.toml.

    Cette fonction lit le fichier pyproject.toml à la racine du projet
    et extrait la version définie dans la section [project].

    Returns:
        str: La version du projet ou "0.1.0" si non trouvée.

    Raises:
        FileNotFoundError: Si le fichier pyproject.toml n'existe pas.
        KeyError: Si la structure du fichier ne contient pas la version.
    """
    try:
        # Chemin vers le fichier pyproject.toml (relatif à ce fichier)
        pyproject_path = Path(__file__).parent / "pyproject.toml"

        # Lecture du fichier avec tomllib (intégré à Python 3.11+)
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)

        # Extraction de la version
        version = pyproject_data.get("project", {}).get("version", "0.1.0")
        return version
    except (FileNotFoundError, KeyError) as e:
        logging.warning(f"Erreur lors de la lecture de la version: {e}")
        return "0.1.0"  # Version par défaut


def get_logger(name: str) -> logging.Logger:
    """
    Crée un logger avec le nom spécifié.

    Args:
        name (str): Nom du logger.

    Returns:
        logging.Logger: Instance de logger configurée.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
