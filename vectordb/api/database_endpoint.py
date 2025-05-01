from fastapi import APIRouter, HTTPException, Body
from vectordb.src.database import (
    get_db,
    Document,
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    add_documents,
    delete_document,
    update_document,
)
from typing import List


router = APIRouter()


@router.post(
    "/add_document",
    summary="Ajouter des documents",
    response_model=List[DocumentResponse],
)
async def add_documents_endpoint(documents: List[DocumentCreate] = Body(...)):
    """Ajoute une liste de documents à la base de données.
    
    Args:
        documents: Liste des documents à ajouter.
        
    Returns:
        Liste des documents ajoutés avec leurs IDs.
        
    Raises:
        ValueError: Si une erreur survient lors de l'ajout des documents.
    """
    results = add_documents(documents)
    if results["errors"]:
        raise ValueError(f"Erreur lors de l'ajout des documents : {results['errors']}")
    print(f"Documents ajoutés : {results['added']}")
    return [
        {
            "id": doc["id"],
            "title": doc["title"],
            "content": doc.get(
                "content", ""
            ),  # Si le contenu est vide, utilisez une chaîne vide
            "theme": doc.get("theme", ""),
            "document_type": doc.get("document_type", ""),
            "publish_date": doc.get(
                "publish_date"
            ),  # Assurez-vous que cette valeur est une date valide
        }
        for doc in results["added"]
    ]


@router.delete(
    "/delete_document",
    summary="Supprimer un document",
    description="Supprime un document de la base de données en fonction de son ID.",
)
async def delete_document_endpoint(document_id: int):
    """Supprime un document de la base de données.
    
    Args:
        document_id: ID du document à supprimer.
        
    Returns:
        Résultat de l'opération.
    """
    result = delete_document(document_id)
    return result


@router.put(
    "/update_document",
    summary="Mettre à jour un document",
    response_model=DocumentResponse,
)
async def update_document_endpoint(payload: DocumentUpdate = Body(...)):
    """Met à jour un document existant dans la base de données.
    
    Args:
        payload: Données pour mettre à jour le document.
        
    Returns:
        Document mis à jour.
        
    Raises:
        HTTPException: Si le document n'existe pas ou si une erreur survient.
    """
    results = update_document(payload)
    if "error" in results:
        raise HTTPException(status_code=400, detail=results["error"])
    print(f"Document mis à jour : {results}")
    return results


@router.get(
    "/list_documents",
    summary="Lister les documents",
    response_model=List[DocumentResponse],
)
async def list_documents_endpoint():
    """Affiche la liste des documents dans la base de données.
    
    Returns:
        Liste de tous les documents dans la base de données.
    """
    db = next(get_db())
    documents = db.query(Document).all()
    return documents
