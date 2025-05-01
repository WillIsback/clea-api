# tests/test_database_api.py
"""
Tests CRUD du module *database* (end-to-end FastAPI).

Le serveur n’est PAS lancé : on utilise TestClient pour appeler
directement le routeur SQLAlchemy + dépendances.
"""

from __future__ import annotations

import uuid
from datetime import date
from collections.abc import Iterator
import pytest
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

    # Nettoyer après le test
    try:
        yield data  # ⬅️  les tests utilisent « data »
    finally:
        # Teardown : suppression du document
        client.delete(f"{API_DB}/documents/{data['document_id']}")


# --------------------------------------------------------------------------- #
# ------------------------------- TESTS ------------------------------------- #
# --------------------------------------------------------------------------- #


def test_create_document(test_doc: dict, client: TestClient) -> None:
    """Le document et ses 2 chunks sont bien insérés."""
    assert test_doc["chunks"] == 2

    # Vérifier le titre en relisant le document
    doc_id = test_doc["document_id"]
    r = client.get(f"{API_DB}/documents/{doc_id}")
    assert r.status_code == 200, r.text
    assert r.json()["title"].endswith("(pytest)")


def test_read_document(client: TestClient, test_doc: dict):
    """Récupération du document & de ses chunks."""
    doc_id = test_doc["document_id"]

    # GET /documents/{id}
    r_doc = client.get(f"{API_DB}/documents/{doc_id}")
    assert r_doc.status_code == 200
    assert r_doc.json()["id"] == doc_id

    # GET /documents/{id}/chunks
    r_chunks = client.get(f"{API_DB}/documents/{doc_id}/chunks")
    assert r_chunks.status_code == 200
    assert len(r_chunks.json()) == 2


def test_update_add_chunk(client: TestClient, test_doc: dict):
    """Mise à jour du titre + ajout d'un chunk supplémentaire."""
    doc_id = test_doc["document_id"]

    payload = {
        "document_update": {
            "document_id": doc_id,
            "title": "Titre modifié (pytest)",
        },
        "new_chunks": [
            {
                "content": "Chunk ajouté",
                "hierarchy_level": 2,
                "start_char": 28,
                "end_char": 40,
            }
        ],
    }
    r = client.put(f"{API_DB}/documents/{doc_id}", json=payload)
    assert r.status_code == 200

    # Vérifier les modifications
    r_doc = client.get(f"{API_DB}/documents/{doc_id}")
    assert r_doc.json()["title"] == "Titre modifié (pytest)"

    r_chunks = client.get(f"{API_DB}/documents/{doc_id}/chunks")
    assert len(r_chunks.json()) == 3


def test_delete_chunks(client: TestClient, test_doc: dict):
    """Suppression d'un chunk spécifique."""
    doc_id = test_doc["document_id"]
    all_chunks = client.get(f"{API_DB}/documents/{doc_id}/chunks").json()
    chunk_to_delete = all_chunks[0]["id"]

    r = client.delete(
        f"{API_DB}/documents/{doc_id}/chunks",
        params={"chunk_ids": chunk_to_delete},
    )
    assert r.status_code == 200
    assert r.json()["chunks_deleted"] == 1

    remaining = client.get(f"{API_DB}/documents/{doc_id}/chunks").json()
    assert len(remaining) == len(all_chunks) - 1


def test_delete_document(client: TestClient):
    """Cycle complet : insertion ➜ suppression ➜ 404 attendu."""
    # Insert rapide
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
    doc_id = client.post(f"{API_DB}/documents", json=payload).json()["document_id"]

    # Suppression
    r_del = client.delete(f"{API_DB}/documents/{doc_id}")
    assert r_del.status_code == 200

    # 404 attendu
    r_get = client.get(f"{API_DB}/documents/{doc_id}")
    assert r_get.status_code == 404
