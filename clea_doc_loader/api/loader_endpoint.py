from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import List
import os
import tempfile
import shutil
from clea_doc_loader.src import DocsLoader, ExtractedDocument

router = APIRouter()


@router.post(
    "/upload-file",
    summary="Uploader un fichier et le traiter",
    response_model=List[ExtractedDocument],
)
async def upload_and_process_file(
    file: UploadFile = File(..., description="Fichier à traiter"),
    max_length: int = Query(1000, description="Taille maximale d'un chunk"),
    theme: str = Query("Thème générique", description="Thème du document"),
):
    """
    Uploade un fichier, l'extrait et le divise en chunks.

    Args:
        file (UploadFile): Fichier uploadé par l'utilisateur.
        max_length (int): Taille maximale d'un chunk.
        theme (str): Thème du document.

    Returns:
        ExtractionResult: Résultat de l'extraction.
    """
    # Création d'un fichier temporaire pour sauvegarder le fichier uploadé
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename or "uploaded_file")

    try:
        # Sauvegarde du fichier uploadé
        with open(temp_file_path, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        # Chargement et extraction
        loader = DocsLoader(str(temp_file_path))
        docs = list(loader.extract_documents(max_length=max_length))

        if not docs:
            raise HTTPException(
                status_code=422, detail="Aucun contenu extrait du document."
            )

        # Appliquer le thème spécifié
        if theme != "Thème générique":
            for doc in docs:
                doc.theme = theme
        return docs

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors du traitement : {str(e)}"
        )

    finally:
        # Nettoyage du fichier temporaire
        file.file.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
