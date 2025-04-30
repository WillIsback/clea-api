from fastapi import APIRouter, HTTPException, Body
from clea_vectordb.src.database import (
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
    """
    Ajoute une liste de documents à la base de données.

    Chaque document doit contenir les champs suivants :
    - `title`: Titre du document
    - `content`: Contenu du document
    - `theme`: Thème du document
    - `document_type`: Type de document
    - `publish_date`: Date de publication (format ISO)

    Args:
        documents {(List[DocumentCreate])}: Liste des documents à ajouter.

    Returns:
        List[DocumentResponse]: Liste des documents ajoutés avec leurs IDs.
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
    """
    Supprime un document de la base de données.

    Args:
        document_id (int): ID du document à supprimer.

    Returns:
        dict: Résultat de l'opération.
    """
    result = delete_document(document_id)
    return result


@router.put(
    "/update_document",
    summary="Mettre à jour un document",
    response_model=DocumentResponse,
)
async def update_document_endpoint(payload: DocumentUpdate = Body(...)):
    """
    Met à jour un document existant dans la base de données.

    Args:
        payload (DocumentUpdate): Données pour mettre à jour le document.

    Returns:
        DocumentResponse: Document mis à jour.
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
    """
    Affiche la liste des documents dans la base de données.

    - `id (int)`: Identifiant unique du document.
    - `title (str)`: Titre du document.
    - `content (str)`: Contenu du document.
    - `theme (str)`: Thème du document.
    - `document_type (str)`: Type de document.
    - `publish_date (date)`: Date de publication du document.
    - `embedding (Text)`: Représentation vectorielle du contenu du document.
    """
    db = next(get_db())
    documents = db.query(Document).all()
    return documents
