from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from clea_vectordb.api.database_endpoint import router as database_router
from clea_vectordb.api.search_endpoint import router as search_router
from clea_doc_loader.api.loader_endpoint import router as doc_loader_router
from clea_pipeline.api.pipeline_endpoint import router as pipeline_router
from dotenv import load_dotenv
import os
import subprocess

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

POSTGRES_USER = os.getenv("DB_USER")
POSTGRES_PASSWORD = os.getenv("DB_PASSWORD")
POSTGRES_DB = os.getenv("DB_NAME")
POSTGRES_HOST = os.getenv("DB_HOST", "localhost")
POSTGRES_PORT = os.getenv("DB_PORT", "5432")

API_HOST = os.getenv("API_HOST", "localhost")
API_PORT = os.getenv("API_PORT", "8080")

# Chemin vers le fichier favicon
FAVICON_PATH = os.path.join(
    os.path.dirname(__file__), "clea_vectordb", "static", "favicon.ico"
)


def start_postgres() -> bool:
    """
    Démarre le service PostgreSQL en utilisant les variables d'environnement.
    """
    try:
        print("Démarrage de PostgreSQL...")
        subprocess.run(["sudo", "systemctl", "start", "postgresql"], check=True)
        print("PostgreSQL démarré avec succès.")

        # Vérification de la connexion à la base de données
        import psycopg2

        conn = psycopg2.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
        )
        conn.close()
        print(
            f"Connexion réussie à la base de données '{POSTGRES_DB}' sur {POSTGRES_HOST}:{POSTGRES_PORT}."
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors du démarrage de PostgreSQL : {e}")
        return False
    except Exception as e:
        print(f"Erreur de connexion à la base de données : {e}")
        return False


# Créer l'application FastAPI principale
app = FastAPI(
    title="Clea API",
    description="API pour gérer les documents et effectuer des recherches.",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
)

# Ajouter le middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autoriser uniquement votre frontend
    allow_credentials=True,
    allow_methods=[
        "*"
    ],  # Autoriser toutes les méthodes HTTP (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Autoriser tous les en-têtes
)

# Inclure les routes des différents modules
app.include_router(database_router, prefix="/database", tags=["Database"])
app.include_router(search_router, prefix="/search", tags=["Search"])
app.include_router(doc_loader_router, prefix="/doc_loader", tags=["DocLoader"])
app.include_router(pipeline_router, prefix="/pipeline", tags=["Pipeline"])


# Gestionnaires d'erreurs globaux
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        {"error": "Invalid request", "details": exc.errors()}, status_code=422
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        {"error": "Internal server error", "details": str(exc)}, status_code=500
    )


# Point de santé
@app.get("/")
async def root():
    return {"message": "Clea API is running"}


# Initialisation de la base de données
def setup_database():
    """Initialise la base de données et configure pgvector"""
    print("Initialisation de la base de données...")
    from clea_vectordb.src.database import init_db, engine

    init_db()

    # Ajout de l'extension pgvector si elle n'existe pas déjà
    with Session(engine) as session:
        try:
            session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.commit()
            print("Extension pgvector installée avec succès")
        except Exception as e:
            print(f"Erreur lors de l'installation de pgvector: {e}")
            session.rollback()
            return False

        # Ajouter la colonne d'embedding si elle n'existe pas
        try:
            session.execute(
                text(
                    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding vector(768)"
                )
            )
            session.commit()
            print("Colonne d'embedding ajoutée avec succès")
        except Exception as e:
            print(f"Erreur lors de l'ajout de la colonne d'embedding: {e}")
            session.rollback()
            return False

    return True


if __name__ == "__main__":
    print("=== Clea API ===\n")
    if not start_postgres():
        raise RuntimeError("Échec du démarrage de PostgreSQL. Abandon.")

    # Étape 1: Configuration de la base de données
    if not setup_database():
        raise RuntimeError("Échec de la configuration de la base de données. Abandon.")
