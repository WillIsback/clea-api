"""search_endpoint.py – Routes FastAPI pour la recherche."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vectordb.src.database import get_db
from vectordb.src.search import SearchEngine, SearchRequest, SearchResponse

router = APIRouter()
_engine = SearchEngine()  # 1 instance partagée


@router.post(
    "/hybrid_search",
    summary="Recherche hybride (vecteur + filtres)",
    response_model=SearchResponse,
    tags=["Search"],
)
def hybrid_search(
    request: SearchRequest, db: Session = Depends(get_db)
) -> SearchResponse:
    """Retourne les *top k* chunks les plus pertinents.

    Le moteur combine :

    * **Filtres SQL** (theme, `document_type`, dates, `corpus_id`)
    * **Index vectoriel pgvector** *(IVFFLAT ou HNSW)*
    * **Rerank Cross-Encoder** sur un sous-ensemble élargi (*top k × 3*)

    Parameters
    ----------
    request : SearchRequest
        Paramètres de la requête (voir modèle pydantic).
    db : Session
        Session SQLAlchemy injectée par FastAPI.

    Returns
    -------
    dict
        Un JSON brut contenant les résultats de la recherche, structuré comme suit :
        {
            "query": str,
            "topK": int,
            "totalResults": int,
            "results": [
                {
                    "chunkId": int,
                    "documentId": int,
                    "title": str,
                    "content": str,
                    "theme": str,
                    "documentType": str,
                    "publishDate": str,
                    "score": float,
                    "hierarchyLevel": int,
                    "context": {
                        "level0": { "id": int, "content": str } | None,
                        "level1": { "id": int, "content": str } | None,
                        "level2": { "id": int, "content": str } | None
                    }
                }
            ]
        }
    """
    return _engine.hybrid_search(db, request)
