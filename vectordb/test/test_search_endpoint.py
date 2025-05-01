"""
Tests end-to-end du moteur de recherche.

• La fixture « test_docs » crée 3 documents (avec 1 chunk chacun)
• Chaque test appelle l'endpoint /search/hybrid_search
• En fin de session, les documents sont purgés.
"""

from __future__ import annotations
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from main import app  # Point d'entrée FastAPI
from vectordb.src.database import Base, engine

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
API_DB = "/database"
API_SEARCH = "/search"


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
        doc_ids.append(r.json()["document_id"])

    yield doc_ids

    for _id in doc_ids:
        client.delete(f"{API_DB}/documents/{_id}")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def hybrid_search(client: TestClient, **body):
    """
    Effectue un POST sur l’endpoint /search/hybrid_search et vérifie un statut 200.

    Args:
        client (TestClient): Le client FastAPI.
        **body: Le corps de la requête.

    Returns:
        dict[str, Any]: La réponse JSON de l’endpoint.
    """
    r = client.post(f"{API_SEARCH}/hybrid_search", json=body)
    assert r.status_code == 200, r.text
    return r.json()


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
def test_basic_search(client: TestClient, test_docs, corpus_id, query, expect):
    """
    Test de recherche basique.

    Vérifie que la réponse contient au moins un résultat et
    que le contenu du premier résultat contient la chaîne attendue.
    """
    res = hybrid_search(client, query=query, corpus_id=corpus_id, top_k=3)
    assert res["totalResults"] >= 1
    first = res["results"][0]["content"].lower()
    assert expect in first


def test_theme_filter(client: TestClient, test_docs, corpus_id):
    """
    Test du filtre sur le thème.

    Vérifie que tous les résultats retournés correspondent au thème "RH".
    """
    res = hybrid_search(
        client,
        query="mutation",
        corpus_id=corpus_id,
        theme="RH",
        top_k=5,
    )
    assert res["totalResults"] >= 1
    assert all(r["theme"] == "RH" for r in res["results"])


def test_hierarchical_context(client: TestClient, test_docs, corpus_id):
    """
    Test de la récupération du contexte hiérarchique.

    Lorsqu'une recherche hiérarchique est demandée, vérifie que la clé
    "context" est présente (même si vide) et, le cas échéant, qu'elle
    contient au moins un niveau (ex: "level_0", "level_1", …).
    """
    res = hybrid_search(
        client,
        query="Python",
        corpus_id=corpus_id,
        hierarchical=True,
        top_k=1,
    )
    first = res["results"][0]
    # On s'assure que la clé "context" est présente (même si c'est un dict vide)
    assert "context" in first, "Contexte hiérarchique manquant"
    # Si un contexte est retourné, on vérifie qu'il contient au moins un niveau
    if first["context"]:
        assert any(k.startswith("level_") for k in first["context"]), (
            "Aucun niveau hiérarchique trouvé dans le contexte"
        )
