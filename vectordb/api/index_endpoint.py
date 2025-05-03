from fastapi import APIRouter, Path, HTTPException
from ..src.index_manager import (
    create_simple_index,
    drop_index,
    check_index_status,
    check_all_indexes,
)
from ..src.schemas import IndexStatus

router = APIRouter()

# --------------------------------------------------------------------------- #
#  INDEX MANAGEMENT
# --------------------------------------------------------------------------- #


@router.post(
    "/create-index/{corpus_id}",
    summary="Créer un index vectoriel pour un corpus",
    response_model=dict,
)
def create_corpus_index(
    corpus_id: str = Path(..., description="Identifiant UUID du corpus"),
):
    """Crée un index vectoriel pour un corpus spécifique.

    Cette fonction crée un index IVFFLAT simple pour accélérer les recherches
    vectorielles sur le corpus spécifié.

    Args:
        corpus_id: Identifiant UUID du corpus à indexer.

    Returns:
        dict: Résultat de l'opération avec statut et message.

    Raises:
        HTTPException: Si une erreur survient lors de la création de l'index.
    """
    result = create_simple_index(corpus_id)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.delete(
    "/drop-index/{corpus_id}",
    summary="Supprimer l'index vectoriel d'un corpus",
    response_model=dict,
)
def remove_corpus_index(
    corpus_id: str = Path(..., description="Identifiant UUID du corpus"),
):
    """Supprime l'index vectoriel pour un corpus spécifique.

    Args:
        corpus_id: Identifiant UUID du corpus.

    Returns:
        dict: Résultat de l'opération.

    Raises:
        HTTPException: Si une erreur survient lors de la suppression de l'index.
    """
    result = drop_index(corpus_id)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.get(
    "/index-status/{corpus_id}",
    summary="Vérifier l'état de l'index pour un corpus",
    response_model=IndexStatus,
)
def get_index_status(
    corpus_id: str = Path(..., description="Identifiant UUID du corpus"),
) -> IndexStatus:
    """Vérifie l'état de l'index pour un corpus spécifique.

    Args:
        corpus_id: Identifiant UUID du corpus.

    Returns:
        IndexStatus: État de l'index et métadonnées.

    Raises:
        HTTPException: Si une erreur survient lors de la vérification de l'état.
    """
    status = check_index_status(corpus_id)

    if status is None:
        raise HTTPException(
            status_code=404, detail=f"Index introuvable pour le corpus {corpus_id}"
        )

    return IndexStatus(**status)


@router.get(
    "/indexes",
    summary="Vérifier l'état de tous les index vectoriels",
    response_model=dict,
)
def get_all_indexes():
    """Vérifie l'état de tous les index vectoriels.

    Returns:
        dict: État des index pour tous les corpus.
    """
    return check_all_indexes()
