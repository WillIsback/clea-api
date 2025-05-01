from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import List
import os
import tempfile
import shutil
from doc_loader.src import DocsLoader, ExtractedDocument

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

    :param file: Fichier uploadé par l'utilisateur.
    :type file: UploadFile
    :param max_length: Taille maximale d'un chunk, defaults to 1000
    :type max_length: int, optional
    :param theme: Thème du document, defaults to "Thème générique"
    :type theme: str, optional
    :raises HTTPException: Si aucun contenu n'est extrait ou en cas d'erreur de traitement
    :return: Résultat de l'extraction
    :rtype: List[ExtractedDocument]
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
