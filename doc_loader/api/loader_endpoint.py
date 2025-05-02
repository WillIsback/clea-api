from fastapi import APIRouter, HTTPException, UploadFile, File, Query
import os
import tempfile
import shutil

from doc_loader.src import DocsLoader
from vectordb.src.schemas import DocumentWithChunks

router = APIRouter()


@router.post(
    "/upload-file",
    summary="Uploader un fichier et le traiter",
    response_model=DocumentWithChunks,
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
        max_length (int): Taille maximale d'un chunk. Par défaut 1000.
        theme (str): Thème du document. Par défaut "Thème générique".

    Returns:
        List[DocumentWithChunks]: Liste des documents extraits.

    Raises:
        HTTPException: Si une erreur survient lors du traitement ou si aucun contenu n'est extrait.
    """
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename or "uploaded_file")

    try:
        # Sauvegarde du fichier uploadé
        with open(temp_file_path, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        # Chargement et extraction
        loader = DocsLoader(str(temp_file_path))
        docs = loader.extract_documents(max_length=max_length)

        if not docs:
            raise HTTPException(
                status_code=422, detail="Aucun contenu extrait du document."
            )

        # Appliquer le thème spécifié
        docs.document.theme = theme

        return docs

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors du traitement : {str(e)}"
        )

    finally:
        # Nettoyage du fichier temporaire
        file.file.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
