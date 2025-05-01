from fastapi import APIRouter
from vectordb.src.search import SearchEngine, DocumentSearchRequest, SearchResults
from vectordb.src.database import get_db


router = APIRouter()


@router.post(
    "/hybrid_search",
    summary="Rechercher des documents hybride",
    response_model=SearchResults,
    description="Recherche des documents en fonction de la similarité vectorielle et reranking d'une requête et de filtres optionnels.",
)
async def search_documents(search_request: DocumentSearchRequest):
    """Recherche des documents en fonction d'une requête et de filtres optionnels.

    Args:
        search_request (DocumentSearchRequest): La requête de recherche avec ses paramètres.

    Returns:
        SearchResults: Les résultats de la recherche hybride.
    """
    filters = {}
    if search_request.theme:
        filters["theme"] = search_request.theme
    if search_request.document_type:
        filters["document_type"] = search_request.document_type
    if search_request.start_date:
        filters["start_date"] = search_request.start_date
    if search_request.end_date:
        filters["end_date"] = search_request.end_date

    print(
        f"Recherche avec les paramètres : query={search_request.query}, filters={filters}, top_k={search_request.top_k}"
    )

    db = next(get_db())
    search_engine = SearchEngine()
    results = search_engine.hybrid_search(
        db, search_request.query, filters=filters, top_k=search_request.top_k
    )
    print(f"Résultats bruts de la recherche : {results}")
    return results
