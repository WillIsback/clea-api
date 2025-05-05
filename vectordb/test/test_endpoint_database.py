# tests/test_database_api.py
"""
Tests CRUD du module *database* (end-to-end FastAPI).

Le serveur n’est PAS lancé : on utilise TestClient pour appeler
directement le routeur SQLAlchemy + dépendances.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from collections.abc import Iterator
import pytest
from typing import Any
from fastapi.testclient import TestClient

# ------------------------------------------------- #
#  ▶  L’application FastAPI “réelle” à importer
# ------------------------------------------------- #
from main import app  #  ⬅️  votre entry-point
from vectordb.src.database import Base, engine  # pour reset la DB

# ------------------------------------------------- #
#  Paramètres globaux
# ------------------------------------------------- #
API_DB = "/database"


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
    log_path = "vectordb/test/log/database_endpoint_responses.log"
    with open(log_path, "w") as f:
        f.write(
            "=== Log des réponses d'endpoint database de la session de test ===\n\n"
        )
    return log_path


# --------------------------------------------------------------------------- #
# ---------------------------- FIXTURES ------------------------------------- #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Client HTTP synchrone ↔️ l’app FastAPI."""
    # Base “neuve” pour la session de test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    # On laisse la BDD telle qu’elle est à la fin de la session


@pytest.fixture(scope="function")
def test_doc(client: TestClient) -> Iterator[dict]:
    """Insère un document minimal + 2 chunks, retourne la réponse JSON."""
    corpus_id = str(uuid.uuid4())

    payload = {
        "document": {
            "title": "Document de test (pytest)",
            "theme": "Test",
            "document_type": "TEST",
            "publish_date": date.today().isoformat(),
            "corpus_id": corpus_id,
        },
        "chunks": [
            {
                "content": "Premier chunk",
                "hierarchy_level": 1,
                "start_char": 0,
                "end_char": 12,
            },
            {
                "content": "Deuxième chunk",
                "hierarchy_level": 1,
                "start_char": 13,
                "end_char": 27,
            },
        ],
    }

    r = client.post(f"{API_DB}/documents", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    log_request_response(
        "POST",
        f"{API_DB}/documents",
        payload,
        r,
        "vectordb/test/log/database_endpoint_responses.log",
    )

    # Nettoyer après le test
    try:
        yield data  # ⬅️  les tests utilisent « data »
    finally:
        # Teardown : suppression du document
        client.delete(f"{API_DB}/documents/{data['id']}")


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


# --------------------------------------------------------------------------- #
# ------------------------------- TESTS ------------------------------------- #
# --------------------------------------------------------------------------- #


def test_create_document(test_doc: dict, client: TestClient, log_file: str) -> None:
    """
    Vérifie que le document et ses 2 chunks sont bien insérés.

    Le titre doit se terminer par "(pytest)".
    """
    assert test_doc["chunkCount"] == 2
    doc_id = test_doc["id"]
    r = client.get(f"{API_DB}/documents/{doc_id}")
    assert r.status_code == 200, r.text
    assert r.json()["title"].endswith("(pytest)")


def test_read_document(client: TestClient, test_doc: dict, log_file: str):
    """
    Récupère le document et ses chunks.

    Vérifie que l’identifiant du document lu correspond et
    que le nombre de chunks est correct.
    """
    doc_id = test_doc["id"]
    r_doc = client.get(f"{API_DB}/documents/{doc_id}")
    log_request_response(
        "GET",
        f"{API_DB}/documents/{doc_id}",
        None,
        r_doc,
        log_file,
    )
    assert r_doc.status_code == 200
    assert r_doc.json()["id"] == doc_id

    r_chunks = client.get(f"{API_DB}/documents/{doc_id}/chunks")
    log_request_response(
        "GET",
        f"{API_DB}/documents/{doc_id}",
        None,
        r_chunks,
        log_file,
    )
    assert r_chunks.status_code == 200
    assert len(r_chunks.json()) == 2


def test_update_add_chunk(client: TestClient, test_doc: dict, log_file: str):
    """
    Met à jour le titre du document et ajoute un chunk supplémentaire.

    Vérifie ensuite que le titre a été modifié et que le nombre total
    de chunks devient 3.
    """
    doc_id = test_doc["id"]
    payload = {
        "document": {
            "id": doc_id,
            "title": "Titre modifié (pytest)",
        },
        "newChunks": [
            {
                "content": "Chunk ajouté",
                "hierarchyLevel": 2,
                "startChar": 28,
                "endChar": 40,
            }
        ],
    }
    r = client.put(f"{API_DB}/documents/{doc_id}", json=payload)
    log_request_response(
        "PUT",
        f"{API_DB}/documents/{doc_id}",
        payload,
        r,
        log_file,
    )
    assert r.status_code == 200

    r_doc = client.get(f"{API_DB}/documents/{doc_id}")
    assert r_doc.json()["title"] == "Titre modifié (pytest)"

    r_chunks = client.get(f"{API_DB}/documents/{doc_id}/chunks")
    assert len(r_chunks.json()) == 3


def test_delete_chunks(client: TestClient, test_doc: dict, log_file: str):
    """
    Supprime un chunk spécifique d’un document.

    Vérifie que le nombre de chunks est décrémenté d’un.
    """
    doc_id = test_doc["id"]
    all_chunks = client.get(f"{API_DB}/documents/{doc_id}/chunks").json()
    chunk_to_delete = all_chunks[0]["id"]

    r = client.delete(
        f"{API_DB}/documents/{doc_id}/chunks",
        params={"chunk_ids": chunk_to_delete},
    )
    log_request_response(
        "DELETE",
        f"{API_DB}/documents/{doc_id}/chunks",
        {"chunk_ids": chunk_to_delete},
        r,
        log_file,
    )
    assert r.status_code == 200
    assert r.json()["chunks_deleted"] == 1

    remaining = client.get(f"{API_DB}/documents/{doc_id}/chunks").json()
    assert len(remaining) == len(all_chunks) - 1


def test_delete_document(client: TestClient, log_file: str):
    """
    Cycle complet : insertion d’un document puis suppression.

    Après suppression, une tentative de lecture doit renvoyer un 404.
    """
    payload = {
        "document": {
            "title": "Temp doc",
            "theme": "Temp",
            "document_type": "TMP",
            "publish_date": date.today().isoformat(),
            "corpus_id": str(uuid.uuid4()),
        },
        "chunks": [],
    }
    r_post = client.post(f"{API_DB}/documents", json=payload)
    log_request_response(
        "POST",
        f"{API_DB}/documents",
        payload,
        r_post,
        log_file,
    )
    doc_id = r_post.json()["id"]

    r_del = client.delete(f"{API_DB}/documents/{doc_id}")
    assert r_del.status_code == 200

    r_get = client.get(f"{API_DB}/documents/{doc_id}")
    assert r_get.status_code == 404
