# api/database_endpoint.py
"""
CRUD routes for documents / chunks.

All request and response bodies are defined in vectordb.src.schemas
(the SQL-Alchemy models stay in database.py).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from vectordb.src.database import (
    Chunk,
    Document,
    get_db,
)

from vectordb.src.crud import (
    add_document_with_chunks,
    delete_document_chunks,
    update_document_with_chunks,
    delete_document,
)

from vectordb.src.schemas import (
    DocumentResponse,
    DocumentWithChunks,
    UpdateWithChunks,
)

router = APIRouter()


# --------------------------------------------------------------------------- #
#  POST /documents – create one document + chunks
# --------------------------------------------------------------------------- #
@router.post(
    "/documents",
    summary="Ajouter un document avec ses chunks",
    response_model=DocumentResponse,
)
def add_document(
    payload: DocumentWithChunks, db: Session = Depends(get_db)
) -> DocumentResponse:
    """Insère le document puis ses chunks dans une transaction unique.

    Args:
        payload: Objet contenant les données du document et ses chunks.
        db: Session de base de données injectée par dépendance.

    Returns:
        DocumentResponse: Document créé avec le nombre de chunks associés.

    Raises:
        HTTPException: Si une erreur survient pendant l'insertion.
    """
    try:
        payload_dict = payload.to_dict()
        add_document = add_document_with_chunks(
            db, payload.document, payload_dict["chunks"]
        )
        # Utiliser Session.get() au lieu de Query.get()
        doc = db.get(Document, add_document["document_id"])
        if not doc:
            raise HTTPException(404, "Document introuvable")

        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            theme=doc.theme,
            document_type=doc.document_type,
            publish_date=doc.publish_date,
            corpus_id=doc.corpus_id,
            chunk_count=add_document["chunks"],
            index_needed=add_document["index_needed"],
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(400, f"Erreur lors de l'ajout du document: {exc}")


@router.put(
    "/documents/{document_id}",
    summary="Mettre à jour un document (et/ou ajouter des chunks)",
    response_model=DocumentResponse,
)
def update_document(
    payload: UpdateWithChunks,
    document_id: int = Path(
        ..., ge=1, description="Identifiant du document à mettre à jour (>= 1)."
    ),
    db: Session = Depends(get_db),  # Ajout de la dépendance à la session DB
) -> DocumentResponse:
    """Met à jour les métadonnées d'un document et peut ajouter de nouveaux chunks.

    Cette fonction permet de modifier les informations d'un document existant et d'y
    ajouter de nouveaux fragments de texte (chunks) en une seule opération.

    Args:
        payload: Objet de mise à jour contenant le document et éventuellement des nouveaux chunks.
        document_id: Identifiant numérique du document à mettre à jour (≥ 1).
        db: Session de base de données injectée par dépendance.

    Returns:
        DocumentResponse: Document mis à jour avec le nombre total de chunks associés.

    Raises:
        HTTPException:
            - 404: Si le document n'existe pas dans la base
    """
    # aligne le body avec l’URL
    payload.document.id = document_id

    # liste de dict prêts pour la fonction helper
    new_chunks_data = [c.model_dump() for c in (payload.new_chunks or [])]

    result = update_document_with_chunks(payload.document, new_chunks_data)
    if "error" in result:
        raise HTTPException(404, result["error"])

    # -- nombre total de chunks après maj -------------
    chunk_count = (
        result["chunks"]["total"]
        if isinstance(result.get("chunks"), dict)
        else result.get("chunks", 0)
    )

    return DocumentResponse(
        id=result["id"],
        title=result["title"],
        theme=result["theme"],
        document_type=result["document_type"],
        publish_date=result["publish_date"],
        corpus_id=result["corpus_id"],
        chunk_count=chunk_count,
        index_needed=result.get("index_needed", False),
    )


# --------------------------------------------------------------------------- #
#  DELETE /documents/{id}
# --------------------------------------------------------------------------- #
@router.delete(
    "/documents/{document_id}",
    summary="Supprimer un document et tous ses chunks",
    response_model=dict,
)
def remove_document(document_id: int = Path(..., ge=1)) -> dict:
    deleted = delete_document(document_id)
    if "error" in deleted:
        raise HTTPException(404, deleted["error"])
    return deleted


# --------------------------------------------------------------------------- #
#  DELETE /documents/{id}/chunks
# --------------------------------------------------------------------------- #
@router.delete(
    "/documents/{document_id}/chunks",
    summary="Supprimer des chunks d'un document",
    response_model=dict,
)
def remove_chunks(
    *,
    document_id: int = Path(..., ge=1),
    chunk_ids: Optional[List[int]] = Query(
        None,
        description="IDs à supprimer ; vide ⇒ tous les chunks du document",
    ),
) -> dict:
    deleted = delete_document_chunks(document_id, chunk_ids)
    if "error" in deleted:
        raise HTTPException(404, deleted["error"])
    return deleted


# --------------------------------------------------------------------------- #
#  GET /documents – collection
# --------------------------------------------------------------------------- #
@router.get(
    "/documents",
    summary="Lister les documents",
    response_model=List[DocumentResponse],
)
def list_documents(
    *,
    theme: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None, alias="documentType"),
    corpus_id: Optional[str] = Query(None, alias="corpusId"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0),
    db: Session = Depends(get_db),
) -> List[DocumentResponse]:
    """Liste l'ensemble des documents de la base de données avec leur nombre de chunks.

    Cette fonction permet de récupérer un ensemble paginé de documents avec possibilité
    de filtrage sur différents critères.

    Args:
        theme: Filtre optionnel pour le thème du document.
        document_type: Filtre optionnel pour le type du document.
        corpus_id: Filtre optionnel sur l'identifiant du corpus.
        skip: Nombre de documents à ignorer (pour la pagination).
        limit: Nombre maximal de documents à retourner.
        db: Session de base de données fournie par dépendance.

    Returns:
        Liste des documents formatés avec leur nombre de chunks associés.
    """
    q = db.query(Document)
    if theme:
        q = q.filter(Document.theme == theme)
    if document_type:
        q = q.filter(Document.document_type == document_type)
    if corpus_id:
        q = q.filter(Document.corpus_id == corpus_id)

    docs = q.offset(skip).limit(limit).all()

    # Préparer la liste de réponses en incluant le comptage des chunks
    result = []
    for doc in docs:
        # Compter les chunks pour ce document
        chunk_count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()

        # Créer un objet DocumentResponse à partir du document
        doc_response = DocumentResponse(
            id=doc.id,
            title=doc.title,
            theme=doc.theme,
            document_type=doc.document_type,
            publish_date=doc.publish_date,
            corpus_id=doc.corpus_id,
            chunk_count=chunk_count,
            index_needed=doc.index_needed,
        )
        result.append(doc_response)

    return result


# --------------------------------------------------------------------------- #
#  GET /documents/{id}
# --------------------------------------------------------------------------- #
@router.get(
    "/documents/{document_id}",
    summary="Récupérer un document",
    response_model=DocumentResponse,
)
def get_document(
    document_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Récupère un document à partir de son identifiant et le formate en DocumentResponse.

    Args:
        document_id (int): Identifiant du document à récupérer.
        db (Session): Session de base de données fournie par dépendance.

    Returns:
        DocumentResponse: Document formaté avec le nombre de chunks associés.

    Raises:
        HTTPException: Si le document n'existe pas dans la base.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, f"Document {document_id} introuvable")

    # Compter les chunks associés à ce document
    chunk_count = db.query(Chunk).filter(Chunk.document_id == document_id).count()

    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        theme=doc.theme,
        document_type=doc.document_type,
        publish_date=doc.publish_date,
        corpus_id=doc.corpus_id,
        chunk_count=chunk_count,
        index_needed=doc.index_needed,
    )


# --------------------------------------------------------------------------- #
#  GET /documents/{id}/chunks
# --------------------------------------------------------------------------- #
@router.get(
    "/documents/{document_id}/chunks",
    summary="Récupérer les chunks d'un document",
    response_model=list,  # keep the raw list for brevity
)
def get_chunks(
    *,
    document_id: int = Path(..., ge=1),
    hierarchy_level: Optional[int] = Query(None, alias="hierarchyLevel"),
    parent_chunk_id: Optional[int] = Query(None, alias="parentChunkId"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0),
    db: Session = Depends(get_db),
):
    if not db.query(Document.id).filter_by(id=document_id).first():
        raise HTTPException(404, f"Document {document_id} introuvable")

    q = db.query(Chunk).filter_by(document_id=document_id)
    if hierarchy_level is not None:
        q = q.filter(Chunk.hierarchy_level == hierarchy_level)
    if parent_chunk_id is not None:
        q = q.filter(Chunk.parent_chunk_id == parent_chunk_id)

    chunks = q.offset(skip).limit(limit).all()
    return [
        {
            "id": c.id,
            "documentId": c.document_id,
            "content": c.content,
            "startChar": c.start_char,
            "endChar": c.end_char,
            "hierarchyLevel": c.hierarchy_level,
            "parentChunkId": c.parent_chunk_id,
        }
        for c in chunks
    ]
