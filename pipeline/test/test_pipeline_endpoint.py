"""Tests unitaires pour les endpoints de pipeline.

Ce module contient des tests pour vérifier le bon fonctionnement des
opérations de traitement de documents et leur insertion dans la base de données.
"""

from __future__ import annotations
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from typing import Any, Iterator

# ------------------------------------------------- #
#  ▶  L’application FastAPI “réelle” à importer
# ------------------------------------------------- #
from main import app
from vectordb.src.database import Base, engine

API_PIPE = "/pipeline"
API_DB = "/database"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Client HTTP synchrone ↔️ l’app FastAPI."""
    # Base “neuve” pour la session de test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def log_file() -> str:
    """
    Crée (ou écrase) le fichier de log pour les réponses d'endpoint.

    Returns:
        str: Le chemin vers le fichier de log.
    """
    log_path = "pipeline/test/log/pipeline_endpoint_responses.log"
    with open(log_path, "w") as f:
        f.write(
            "=== Log des réponses d'endpoint pipeline de la session de test ===\n\n"
        )
    return log_path


@pytest.fixture(scope="session")
def demo_files() -> dict[str, Path]:
    """
    Charge les fichiers de démonstration pour les tests.

    Returns:
        dict[str, Path]: Dictionnaire des fichiers de démonstration par extension.
    """
    demo_dir = Path("demo")
    files = {ext: demo_dir / f"demo.{ext}" for ext in ["txt", "json", "pdf", "html"]}
    return {ext: path for ext, path in files.items() if path.exists()}


@pytest.fixture
def temp_file(tmp_path):
    """
    Crée un fichier temporaire pour les tests.

    Args:
        tmp_path: Répertoire temporaire fourni par pytest.

    Returns:
        Callable[[str, str], str]: Fonction pour créer un fichier temporaire.
    """

    def _create_temp_file(filename: str, content: str) -> str:
        file_path = tmp_path / filename
        file_path.write_text(content, encoding="utf-8")
        return str(file_path)

    return _create_temp_file


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def log_request_response(
    method: str, url: str, req_body: Any, response, log_file: str
) -> None:
    """Enregistre dans le fichier de log la requête HTTP et la réponse correspondante.

    Args:
        method (str): La méthode HTTP utilisée (GET, POST, PUT, DELETE, etc.).
        url (str): L'URL de la requête.
        req_body (Any): Le corps de la requête envoyé. Peut être None.
        response: Réponse de l'endpoint (objet Response ou directement des données JSON).
        log_file (str): Chemin vers le fichier de log.
    """
    log_entry = {
        "request": {
            "method": method,
            "url": url,
            "body": req_body,
        },
    }
    try:
        log_entry["response"] = response.json()
    except Exception:
        log_entry["response"] = getattr(response, "text", response)
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry, indent=2, ensure_ascii=False) + "\n\n")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("file_type", ["txt"])
def test_process_and_store_endpoint(
    client: TestClient,
    demo_files,
    log_file,
    temp_file,
    file_type: str,
) -> None:
    """
    Teste le traitement et le stockage d'un fichier.

    Args:
        client (TestClient): Client HTTP pour l’application FastAPI.
        demo_files (dict): Fichiers de démonstration disponibles.
        log_file (str): Chemin vers le fichier de log.
        file_type (str): Type de fichier à tester (txt, json, pdf, html).
    """
    if file_type not in demo_files:
        pytest.skip(f"Fichier de démonstration {file_type.upper()} non disponible")

    dry_run = False
    if dry_run:
        # Si le fichier n'existe pas, le créer avec un contenu par défaut
        content = "<html><head><title>Titre</title></head><body>Bonjour Cléa API</body></html>"
        file_path = Path(temp_file(f"test.{file_type}", content))
    else:
        # Sinon, utiliser le fichier de démonstration
        file_path = demo_files[file_type]

    # Paramètres du test
    max_length = 500
    overlap = 100
    theme = "Test"
    # Envoyer la requête au endpoint
    with open(file_path, "rb") as file:
        response = client.post(
            f"{API_PIPE}/process-and-store",
            files={"file": (file_path.name, file, f"application/{file_type}")},
            data={
                "max_length": str(max_length),
                "overlap": str(overlap),
                "theme": theme,
            },
        )
    # Vérifier la réponse
    assert response.status_code == 200, (
        f"Erreur lors du traitement du fichier {file_type.upper()}: {response.text}"
    )
    result = response.json()

    # Vérifier les informations du résultat
    assert "document_id" in result, "La réponse ne contient pas l'ID du document"
    assert "chunks" in result, "La réponse ne contient pas les chunks"
    assert "corpus_id" in result, "La réponse ne contient pas l'ID du corpus"

    # Log de la requête et de la réponse
    log_request_response(
        "POST",
        f"{API_PIPE}/process-and-store",
        {"max_length": max_length, "overlap": overlap, "theme": theme},
        response,
        log_file,
    )

    # Nettoyer
    document_id = result["document_id"]
    client.delete(f"{API_DB}/documents/{document_id}")


def test_process_and_store_async_endpoint(
    client: TestClient, demo_files, log_file, temp_file
) -> None:
    """
    Teste le traitement asynchrone d'un fichier.

    Args:
        client (TestClient): Client HTTP pour l’application FastAPI.
        demo_files (dict): Fichiers de démonstration disponibles.
        log_file (str): Chemin vers le fichier de log.
    """
    file_type = next(iter(demo_files.keys()))
    file_path = demo_files[file_type]

    # Paramètres du test
    # Préparer un fichier HTML
    content = (
        "<html><head><title>Titre</title></head><body>Bonjour Cléa API</body></html>"
    )
    file_path = Path(temp_file("test.html", content))
    theme = "Test Async"
    max_length = 500
    overlap = 100

    # Envoyer la requête au endpoint asynchrone
    with open(file_path, "rb") as file:
        response = client.post(
            f"{API_PIPE}/process-and-store-async",
            files={"file": (file_path.name, file, "application/octet-stream")},
            data={
                "max_length": str(max_length),
                "overlap": str(overlap),
                "theme": theme,
            },
        )

    # Vérifier la réponse
    assert response.status_code == 200, (
        f"Erreur lors du lancement du traitement asynchrone: {response.text}"
    )
    result = response.json()

    # Vérifier les informations de la tâche asynchrone
    assert "task_id" in result, "La réponse ne contient pas l'ID de la tâche"
    assert "status" in result, "La réponse ne contient pas le statut de la tâche"
    assert result["status"] == "processing", (
        "Le statut de la tâche n'est pas 'processing'"
    )

    # Log de la requête et de la réponse
    log_request_response(
        "POST",
        f"{API_PIPE}/process-and-store-async",
        {"max_length": max_length, "overlap": overlap, "theme": theme},
        response,
        log_file,
    )
