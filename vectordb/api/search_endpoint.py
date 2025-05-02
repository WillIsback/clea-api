"""search_endpoint.py – Routes FastAPI pour la recherche."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vectordb.src.database import get_db
from vectordb.src.search import SearchEngine

from vectordb.src.schemas import (
    SearchRequest,
    SearchResponse,
)

router = APIRouter()
_engine = SearchEngine()  # 1 instance partagée


@router.post(
    "/hybrid_search",
    summary="Recherche hybride (vecteur + filtres)",
    response_model=SearchResponse,
)
def hybrid_search(
    request: SearchRequest, db: Session = Depends(get_db)
) -> SearchResponse:
    """Retourne les *top k* chunks les plus pertinents.

    Le moteur combine :

    * **Filtres SQL** (theme, `document_type`, dates, `corpus_id`)
    * **Index vectoriel pgvector** *(IVFFLAT ou HNSW)*
    * **Rerank Cross-Encoder** sur un sous-ensemble élargi (*top k × 3*)

    """
    return _engine.hybrid_search(db, request)
