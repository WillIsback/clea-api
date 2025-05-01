from fastapi import APIRouter, HTTPException, Body, Query, Path, Depends
from sqlalchemy.orm import Session
from vectordb.src.database import (
    get_db,
    Document,
    Chunk,
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    add_document_with_chunks,
    update_document_with_chunks,
    delete_document,
    delete_document_chunks,
    create_index_for_corpus,
)
from typing import List, Dict, Any, Optional


router = APIRouter()


@router.post(
    "/documents",
    summary="Ajouter un document avec ses chunks",
    response_model=Dict[str, Any],
    description="Ajoute un document et ses chunks hiérarchiques à la base de données.",
)
async def add_document_endpoint(
    document: DocumentCreate = Body(...),
    chunks: List[Dict[str, Any]] = Body(...),
    db: Session = Depends(get_db),
):
    """Ajoute un document et ses chunks hiérarchiques à la base de données.

    Args:
        document: Données du document à créer.
        chunks: Liste des chunks avec leur contenu et métadonnées hiérarchiques.
        db: Session de base de données.

    Returns:
        Dict[str, Any]: Résultat de l'opération avec l'ID du document et des informations sur les chunks.

    Raises:
        HTTPException: Si une erreur survient lors de l'ajout du document ou des chunks.
    """
    try:
        result = add_document_with_chunks(db, document, chunks)

        # Si l'index doit être créé, proposer sa création
        if result.get("create_index"):
            corpus_id = result.get("corpus_id")
            # Création asynchrone de l'index peut être lancée ici
            # Ou simplement suggérer la création via l'API
            result["index_message"] = (
                f"Un nouvel index pour le corpus {corpus_id} devrait être créé. "
                f"Utilisez l'endpoint /indexes/{corpus_id}/create pour créer l'index."
            )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Erreur lors de l'ajout du document: {str(e)}"
        )


@router.put(
    "/documents/{document_id}",
    summary="Mettre à jour un document existant",
    response_model=Dict[str, Any],
    description="Met à jour un document existant et peut ajouter de nouveaux chunks.",
)
async def update_document_endpoint(
    document_id: int = Path(..., description="ID du document à mettre à jour"),
    document_update: DocumentUpdate = Body(...),
    new_chunks: Optional[List[Dict[str, Any]]] = Body(None),
):
    """Met à jour un document existant et peut ajouter de nouveaux chunks.

    Args:
        document_id: ID du document à mettre à jour.
        document_update: Données de mise à jour du document.
        new_chunks: Nouveaux chunks à ajouter (optionnel).

    Returns:
        Dict[str, Any]: Résultat de l'opération avec les informations sur le document et les chunks.

    Raises:
        HTTPException: Si le document n'existe pas ou si une erreur survient.
    """
    # S'assurer que l'ID dans le chemin et l'ID dans le payload correspondent
    document_update.document_id = document_id

    try:
        result = update_document_with_chunks(document_update, new_chunks)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de la mise à jour du document: {str(e)}",
        )


@router.delete(
    "/documents/{document_id}",
    summary="Supprimer un document",
    response_model=Dict[str, Any],
    description="Supprime un document de la base de données avec tous ses chunks associés.",
)
async def delete_document_endpoint(
    document_id: int = Path(..., description="ID du document à supprimer"),
):
    """Supprime un document de la base de données avec tous ses chunks associés.

    Args:
        document_id: ID du document à supprimer.

    Returns:
        Dict[str, Any]: Résultat de l'opération.

    Raises:
        HTTPException: Si le document n'existe pas ou si une erreur survient.
    """
    result = delete_document(document_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete(
    "/documents/{document_id}/chunks",
    summary="Supprimer des chunks d'un document",
    response_model=Dict[str, Any],
    description="Supprime des chunks spécifiques d'un document ou tous les chunks si aucun ID n'est spécifié.",
)
async def delete_chunks_endpoint(
    document_id: int = Path(..., description="ID du document"),
    chunk_ids: Optional[List[int]] = Query(
        None,
        description="Liste des IDs des chunks à supprimer (si vide, supprime tous les chunks)",
    ),
):
    """Supprime des chunks spécifiques d'un document ou tous les chunks si aucun ID n'est spécifié.

    Args:
        document_id: ID du document.
        chunk_ids: Liste des IDs des chunks à supprimer (si None, supprime tous les chunks).

    Returns:
        Dict[str, Any]: Résultat de l'opération avec le nombre de chunks supprimés.

    Raises:
        HTTPException: Si le document n'existe pas ou si une erreur survient.
    """
    result = delete_document_chunks(document_id, chunk_ids)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get(
    "/documents",
    summary="Lister les documents",
    response_model=List[DocumentResponse],
    description="Récupère la liste des documents avec filtrage optionnel par thème, type ou corpus.",
)
async def list_documents_endpoint(
    theme: Optional[str] = Query(None, description="Filtrer par thème"),
    document_type: Optional[str] = Query(
        None, description="Filtrer par type de document"
    ),
    corpus_id: Optional[str] = Query(None, description="Filtrer par corpus"),
    skip: int = Query(0, description="Nombre de documents à sauter (pagination)"),
    limit: int = Query(100, description="Nombre maximum de documents à retourner"),
    db: Session = Depends(get_db),
):
    """Récupère la liste des documents avec filtrage optionnel.

    Args:
        theme: Filtrer par thème.
        document_type: Filtrer par type de document.
        corpus_id: Filtrer par corpus.
        skip: Nombre de documents à sauter (pagination).
        limit: Nombre maximum de documents à retourner.
        db: Session de base de données.

    Returns:
        List[DocumentResponse]: Liste des documents correspondant aux critères.
    """
    # Construire la requête de base
    query = db.query(Document)

    # Appliquer les filtres si spécifiés
    if theme:
        query = query.filter(Document.theme == theme)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    if corpus_id:
        query = query.filter(Document.corpus_id == corpus_id)

    # Récupérer les documents avec pagination
    documents = query.offset(skip).limit(limit).all()

    # Pour chaque document, compter le nombre de chunks associés
    result = []
    for doc in documents:
        chunk_count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()
        doc_dict = {
            "id": doc.id,
            "title": doc.title,
            "theme": doc.theme,
            "document_type": doc.document_type,
            "publish_date": doc.publish_date,
            "corpus_id": doc.corpus_id,
            "chunk_count": chunk_count,
        }
        result.append(doc_dict)

    return result


@router.get(
    "/documents/{document_id}",
    summary="Récupérer un document",
    response_model=DocumentResponse,
    description="Récupère les détails d'un document spécifique.",
)
async def get_document_endpoint(
    document_id: int = Path(..., description="ID du document à récupérer"),
    db: Session = Depends(get_db),
):
    """Récupère les détails d'un document spécifique.

    Args:
        document_id: ID du document à récupérer.
        db: Session de base de données.

    Returns:
        DocumentResponse: Détails du document.

    Raises:
        HTTPException: Si le document n'existe pas.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document avec ID {document_id} introuvable"
        )

    # Compter le nombre de chunks associés
    chunk_count = db.query(Chunk).filter(Chunk.document_id == document_id).count()

    doc_response = {
        "id": document.id,
        "title": document.title,
        "theme": document.theme,
        "document_type": document.document_type,
        "publish_date": document.publish_date,
        "corpus_id": document.corpus_id,
        "chunk_count": chunk_count,
    }

    return doc_response


@router.get(
    "/documents/{document_id}/chunks",
    summary="Récupérer les chunks d'un document",
    response_model=List[Dict[str, Any]],
    description="Récupère les chunks d'un document avec filtrage hiérarchique optionnel.",
)
async def get_document_chunks_endpoint(
    document_id: int = Path(..., description="ID du document"),
    hierarchy_level: Optional[int] = Query(
        None, description="Filtrer par niveau hiérarchique (0-3)"
    ),
    parent_chunk_id: Optional[int] = Query(
        None, description="Filtrer par chunk parent"
    ),
    skip: int = Query(0, description="Nombre de chunks à sauter"),
    limit: int = Query(100, description="Nombre maximum de chunks à retourner"),
    db: Session = Depends(get_db),
):
    """Récupère les chunks d'un document avec filtrage hiérarchique optionnel.

    Args:
        document_id: ID du document.
        hierarchy_level: Filtrer par niveau hiérarchique (0: document, 1: section, 2: paragraphe, 3: chunk).
        parent_chunk_id: Filtrer par chunk parent.
        skip: Nombre de chunks à sauter (pagination).
        limit: Nombre maximum de chunks à retourner.
        db: Session de base de données.

    Returns:
        List[Dict[str, Any]]: Liste des chunks correspondant aux critères.

    Raises:
        HTTPException: Si le document n'existe pas.
    """
    # Vérifier que le document existe
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document avec ID {document_id} introuvable"
        )

    # Construire la requête de base
    query = db.query(Chunk).filter(Chunk.document_id == document_id)

    # Appliquer les filtres si spécifiés
    if hierarchy_level is not None:
        query = query.filter(Chunk.hierarchy_level == hierarchy_level)

    if parent_chunk_id is not None:
        query = query.filter(Chunk.parent_chunk_id == parent_chunk_id)

    # Récupérer les chunks avec pagination
    chunks = query.offset(skip).limit(limit).all()

    # Formater les résultats (sans inclure les embeddings pour alléger la réponse)
    result = []
    for chunk in chunks:
        chunk_dict = {
            "id": chunk.id,
            "document_id": chunk.document_id,
            "content": chunk.content,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "hierarchy_level": chunk.hierarchy_level,
            "parent_chunk_id": chunk.parent_chunk_id,
        }
        result.append(chunk_dict)

    return result


@router.post(
    "/indexes/{corpus_id}/create",
    summary="Créer un index vectoriel pour un corpus",
    response_model=Dict[str, Any],
    description="Crée un index vectoriel pour un corpus spécifique.",
)
async def create_index_endpoint(
    corpus_id: str = Path(..., description="ID du corpus"),
    index_type: str = Query(
        "auto", description="Type d'index ('ivfflat', 'hnsw' ou 'auto')"
    ),
    force: bool = Query(
        False, description="Forcer la recréation de l'index s'il existe déjà"
    ),
):
    """Crée un index vectoriel pour un corpus spécifique.

    Args:
        corpus_id: ID du corpus pour lequel créer l'index.
        index_type: Type d'index ('ivfflat', 'hnsw' ou 'auto').
        force: Si True, recréera l'index même s'il existe déjà.

    Returns:
        Dict[str, Any]: Résultat de l'opération.

    Raises:
        HTTPException: Si une erreur survient lors de la création de l'index.
    """
    result = create_index_for_corpus(corpus_id, index_type, force)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
