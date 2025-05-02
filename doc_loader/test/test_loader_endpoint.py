"""
Tests du endpoint d'upload et de traitement de documents (loader_endpoint.py).

On utilise TestClient pour appeler directement le router de FastAPI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from main import app
from typing import Any
import json

API_PATH = "/doc_loader/upload-file"


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Fournit un client HTTP pour l’application FastAPI.

    Returns:
        TestClient: Client pour envoyer des requêtes à l'application.
    """
    return TestClient(app)


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
# Fixture pour le fichier de log (écrase à chaque session de test)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session", autouse=True)
def log_file() -> str:
    """
    Crée (ou écrase) le fichier de log pour les réponses d'endpoint.

    Returns:
        str: Le chemin vers le fichier de log.
    """
    log_path = "doc_loader/test/log/doc_loader_endpoint_responses.log"
    with open(log_path, "w") as f:
        f.write(
            "=== Log des réponses d'endpoint database de la session de test ===\n\n"
        )
    return log_path


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
    # Récupération de la réponse
    try:
        resp_content = response.json()
    except Exception:
        resp_content = getattr(response, "text", response)
    log_entry["response"] = resp_content

    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry, indent=2, ensure_ascii=False) + "\n\n")


def test_upload_file_txt(client: TestClient, temp_file, log_file) -> None:
    """
    Teste l’endpoint upload-file avec un fichier texte simple.

    Args:
        client (TestClient): Client HTTP pour l’application FastAPI.
        temp_file (Callable): Fonction pour créer un fichier temporaire.

    Returns:
        None
    """
    # Préparer un fichier texte
    content = "Bonjour Cléa API"
    file_path = temp_file("test.txt", content)

    # Appel de l’API
    with open(file_path, "rb") as f:
        files = {"file": ("test.txt", f, "text/plain")}
        params = {"max_length": 100, "theme": "MonThèmeTest"}
        response = client.post(API_PATH, files=files, params=params)

    # Assertions principales
    assert response.status_code == 200, response.text
    data = response.json()
    log_request_response(
        "POST",
        API_PATH,
        {"max_length": 100, "theme": "MonThèmeTest"},
        response,
        log_file,
    )
    assert len(data["chunks"]) == 1, "Un seul document attendu pour un contenu court."
    assert len(data["chunks"][0]["content"]) > 0, (
        "Le contenu retourné doit être non vide."
    )
    doc = data["document"]
    assert doc["theme"] == "MonThèmeTest", (
        "Le thème doit être celui passé en paramètre."
    )
    assert doc["documentType"] == "TXT", "Le type de document doit être TXT."


def test_upload_file_html(client: TestClient, temp_file, log_file) -> None:
    """
    Teste l’endpoint upload-file avec un fichier HTML.

    Args:
        client (TestClient): Client HTTP pour l’application FastAPI.
        temp_file (Callable): Fonction pour créer un fichier temporaire.

    Returns:
        None
    """
    # Préparer un fichier HTML
    content = (
        "<html><head><title>Titre</title></head><body>Bonjour Cléa API</body></html>"
    )
    file_path = temp_file("test.html", content)

    # Appel de l’API
    with open(file_path, "rb") as f:
        files = {"file": ("test.html", f, "text/html")}
        params = {"max_length": 100, "theme": "MonThèmeHTML"}
        response = client.post(API_PATH, files=files, params=params)

    # Assertions principales
    assert response.status_code == 200, response.text
    data = response.json()
    log_request_response(
        "POST",
        API_PATH,
        {"max_length": 100, "theme": "MonThèmeHTML"},
        response,
        log_file,
    )
    assert len(data["chunks"]) == 1, "Un seul document attendu pour un contenu court."
    assert len(data["chunks"][0]["content"]) > 0, (
        "Le contenu retourné doit être non vide."
    )
    doc = data["document"]
    assert doc["theme"] == "MonThèmeHTML", (
        "Le thème doit être celui passé en paramètre."
    )
    assert doc["documentType"] == "HTML", "Le type de document doit être HTML."


def test_upload_file_demo(client: TestClient, temp_file, log_file) -> None:
    file_path = "demo/demo.txt"
    # Appel de l’API
    with open(file_path, "rb") as f:
        files = {"file": ("test.txt", f, "text/plain")}
        params = {"max_length": 1000, "theme": "MonThèmeTest"}
        response = client.post(API_PATH, files=files, params=params)

    # Assertions principales
    assert response.status_code == 200, response.text
    data = response.json()
    log_request_response(
        "POST",
        API_PATH,
        {"max_length": 1000, "theme": "MonThèmeTest"},
        response,
        log_file,
    )


def test_upload_file_invalid(client: TestClient, temp_file) -> None:
    """
    Teste l’endpoint upload-file avec un fichier non supporté.

    Args:
        client (TestClient): Client HTTP pour l’application FastAPI.
        temp_file (Callable): Fonction pour créer un fichier temporaire.

    Returns:
        None
    """
    # Préparer un fichier avec une extension non supportée
    content = "Contenu non supporté"
    file_path = temp_file("test.xyz", content)

    # Appel de l’API
    with open(file_path, "rb") as f:
        files = {"file": ("test.xyz", f, "application/octet-stream")}
        response = client.post(API_PATH, files=files)

    # Assertions principales
    assert response.status_code == 500, response.text
