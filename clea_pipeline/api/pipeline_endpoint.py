from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from clea_pipeline.src.pipeline import process_and_store
from typing import List, Dict
import tempfile
import shutil
import os

router = APIRouter()


@router.post(
    "/process-and-store",
    summary="Charger un fichier, l'extraire et l'insérer dans la base de données",
    response_model=List[Dict],
)
async def process_and_store_endpoint(
    file: UploadFile = File(..., description="Fichier à traiter"),
    max_length: int = Query(1000, description="Taille maximale d'un chunk"),
    theme: str = Query("Thème générique", description="Thème du document"),
):
    """
    Charge un fichier, extrait les documents et les insère dans la base de données.

    Args:
        file (UploadFile): Fichier uploadé par l'utilisateur.
        max_length (int): Taille maximale d'un chunk.
        theme (str): Thème à appliquer aux documents.

    Returns:
        List[Dict]: Liste des documents ajoutés avec leurs IDs.
    """
    # Sauvegarde temporaire du fichier
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename or "uploaded_file")

    try:
        with open(temp_file_path, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        # Appel de la fonction pipeline
        result = process_and_store(temp_file_path, max_length, theme)

        print(f"Documents ajoutés : {result['added']}")
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
            for doc in result["added"]
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors du traitement : {str(e)}"
        )

    finally:
        file.file.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
