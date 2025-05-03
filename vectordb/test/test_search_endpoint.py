"""
Tests end-to-end du moteur de recherche.

• La fixture « test_docs » crée 3 documents (avec 1 chunk chacun)
• Chaque test appelle l'endpoint /search/hybrid_search
• En fin de session, les documents sont purgés.
"""

from __future__ import annotations
import json
import uuid
from collections.abc import Iterator
from typing import Any
import pytest
from fastapi.testclient import TestClient

from main import app  # Point d'entrée FastAPI
from vectordb.src.database import (
    Base,
    engine,
)


# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
API_DB = "/database"
API_SEARCH = "/search"


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
    log_path = "vectordb/test/log/search_endpoint_responses.log"
    with open(log_path, "w") as f:
        f.write("=== Log des réponses d'endpoint search de la session de test ===\n\n")
    return log_path


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """
    Crée un client HTTP synchrone branché sur l’application FastAPI.

    Returns:
        Iterator[TestClient]: Le client TestClient.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def corpus_id() -> str:
    """
    Fournit un identifiant de corpus commun aux documents de test.

    Returns:
        str: Un identifiant unique de corpus.
    """
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def test_docs(client: TestClient, corpus_id: str) -> Iterator[list[int]]:
    """
    Insère 3 documents (chacun avec un chunk) et retourne la liste de leurs identifiants.
    En fin de session, purge les documents insérés.

    Returns:
        Iterator[list[int]]: Liste des identifiants des documents insérés.
    """
    docs_payload = [
        {
            "title": "Guide frais professionnels (TEST)",
            "content": (
                "Les frais professionnels doivent être soumis dans le mois "
                "suivant leur engagement avec justificatifs."
            ),
            "theme": "Finance",
            "document_type": "Guide",
            "publish_date": "2025-01-01",
        },
        {
            "title": "Procédure mutation interne (TEST)",
            "content": (
                "Les salariés souhaitant effectuer une mutation interne "
                "doivent avoir passé au moins 18 mois à leur poste actuel."
            ),
            "theme": "RH",
            "document_type": "Procédure",
            "publish_date": "2025-02-15",
        },
        {
            "title": "Introduction à la programmation Python (TEST)",
            "content": (
                "Ce document explique les bases de Python : variables, "
                "boucles, fonctions…"
            ),
            "theme": "Informatique",
            "document_type": "Tutoriel",
            "publish_date": "2025-03-10",
        },
    ]

    doc_ids: list[int] = []

    for doc in docs_payload:
        body = {
            "document": {
                **doc,
                "corpus_id": corpus_id,
            },
            "chunks": [
                {
                    "content": doc["content"],
                    "hierarchy_level": 3,
                    "start_char": 0,
                    "end_char": len(doc["content"]),
                }
            ],
        }
        r = client.post(f"{API_DB}/documents", json=body)
        assert r.status_code == 200, r.text
        doc_ids.append(r.json()["id"])
        log_request_response(
            "POST",
            f"{API_DB}/documents",
            body,
            r,
            "vectordb/test/log/database_endpoint_responses.log",
        )
    yield doc_ids

    for _id in doc_ids:
        client.delete(f"{API_DB}/documents/{_id}")
        log_request_response(
            "DELETE",
            f"{API_DB}/documents/{_id}",
            None,
            {},
            "vectordb/test/log/database_endpoint_responses.log",
        )
    # Purge des documents insérés


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
# Helpers
# --------------------------------------------------------------------------- #
def hybrid_search(client: TestClient, log_file: str, **body):
    """
    Effectue un POST sur l’endpoint /search/hybrid_search, écrit la réponse dans le fichier de log,
    et vérifie un statut 200.

    Args:
        client (TestClient): Le client FastAPI.
        log_file (str): Chemin vers le fichier de log.
        **body: Le corps de la requête.

    Returns:
        dict[str, Any]: La réponse JSON de l’endpoint.
    """
    r = client.post(f"{API_SEARCH}/hybrid_search", json=body)
    assert r.status_code == 200, r.text
    response = r.json()
    log_request_response(
        "POST",
        f"{API_SEARCH}/hybrid_search",
        body,
        r,
        log_file,
    )
    return response


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("query", "expect"),
    [
        ("programmation Python", "python"),
        ("frais professionnels", "frais"),
    ],
)
def test_basic_search(
    client: TestClient, test_docs, corpus_id, log_file, query, expect
):
    """
    Test de recherche basique.

    Vérifie que la réponse contient au moins un résultat et
    que le contenu du premier résultat contient la chaîne attendue.
    """
    res = hybrid_search(client, log_file, query=query, corpus_id=corpus_id, top_k=3)
    assert res["totalResults"] >= 1
    first = res["results"][0]["content"].lower()
    assert expect in first


def test_theme_filter(client: TestClient, test_docs, corpus_id, log_file):
    """
    Test du filtre sur le thème.

    Vérifie que tous les résultats retournés correspondent au thème "RH".
    """
    res = hybrid_search(
        client, log_file, query="mutation", corpus_id=corpus_id, theme="RH", top_k=5
    )
    assert res["totalResults"] >= 1
    assert all(r["theme"] == "RH" for r in res["results"])


def test_hierarchical_context(client: TestClient, test_docs, corpus_id, log_file):
    """
    Test de la récupération du contexte hiérarchique.

    Lorsqu'une recherche hiérarchique est demandée, vérifie que la clé
    "context" est présente (même si vide) et, le cas échéant, qu'elle
    contient au moins un niveau (ex: "level_0", "level_1", …).
    """
    res = hybrid_search(
        client,
        log_file,
        query="Python",
        corpus_id=corpus_id,
        hierarchical=True,
        top_k=1,
    )
    first = res["results"][0]
    log_request_response(
        "POST",
        f"{API_SEARCH}/hybrid_search",
        {"query": "Python", "corpus_id": corpus_id, "hierarchical": True},
        res,
        log_file,
    )
    assert "context" in first, "Contexte hiérarchique manquant"
    if first["context"]:
        assert any(k.startswith("level_") for k in first["context"]), (
            "Aucun niveau hiérarchique trouvé dans le contexte"
        )
