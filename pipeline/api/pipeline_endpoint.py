from fastapi import APIRouter, HTTPException, UploadFile, File, Query, BackgroundTasks
from pipeline.src.pipeline import process_and_store
from typing import Dict, Optional, Any
import tempfile
import shutil
import os
import logging
import uuid
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


class RagQueryRequest(BaseModel):
    """Requête pour interroger la base de connaissances avec RAG.
    
    Args:
        query: Question en langage naturel à poser au système.
        filters: Filtres optionnels pour la recherche documentaire.
        model_name: Nom du modèle LLM à utiliser.
        prompt_type: Type de prompt à utiliser.
        stream: Indique si la réponse doit être générée en streaming.
        max_docs: Nombre maximum de documents à utiliser.
        
    Attributes:
        query: Question en langage naturel.
        filters: Filtres pour la recherche (thème, type de document, dates...).
        model_name: Nom du modèle LLM à utiliser.
        prompt_type: Type de prompt ('standard', 'summary', 'comparison').
        stream: Si True, la réponse est générée progressivement.
        max_docs: Nombre maximum de documents à utiliser pour le contexte.
    """
    query: str = Field(..., description="Question en langage naturel")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filtres pour la recherche")
    model_name: str = Field("Qwen3-0.6B", description="Modèle LLM à utiliser")
    prompt_type: str = Field("standard", description="Type de prompt (standard, summary, comparison)")
    stream: bool = Field(False, description="Réponse en streaming")
    max_docs: int = Field(5, description="Nombre maximum de documents à utiliser")


@router.post(
    "/process-and-store",
    summary="Charger un fichier, l'extraire et l'insérer dans la base de données avec segmentation adaptative",
    response_model=Dict,
)
async def process_and_store_endpoint(
    file: UploadFile = File(..., description="Fichier à traiter"),
    max_length: int = Query(500, description="Taille maximale d'un chunk"),
    overlap: int = Query(100, description="Chevauchement entre les chunks"),
    theme: str = Query("Thème générique", description="Thème du document"),
    corpus_id: Optional[str] = Query(
        None, description="Identifiant du corpus (généré si non spécifié)"
    ),
):
    """Charge un fichier, l'extrait avec segmentation hiérarchique et l'insère dans la base de données.

    Le fichier est temporairement sauvegardé sur le disque, traité pour en extraire le
    contenu textuel, segmenté selon une approche hiérarchique, puis inséré dans la base
    de données avec génération automatique d'embeddings.

    Args:
        file: Fichier uploadé par l'utilisateur.
        max_length: Taille maximale d'un chunk final.
        overlap: Chevauchement entre les chunks.
        theme: Thème à appliquer au document.
        corpus_id: Identifiant du corpus (généré si non spécifié).

    Returns:
        Dict: Résultats de l'opération avec l'ID du document et les statistiques de segmentation.

    Raises:
        HTTPException: Si une erreur survient pendant le traitement du document.
    """
    # Sauvegarde temporaire du fichier
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename or "uploaded_file")

    file.filename = file.filename or "uploaded_file"

    try:
        with open(temp_file_path, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        # Traiter le document et l'insérer dans la base de données
        result = process_and_store(
            file_path=temp_file_path,
            max_length=max_length,
            overlap=overlap,
            theme=theme,
            corpus_id=corpus_id,
        )

        # Ajouter des informations sur le fichier original
        result["original_filename"] = file.filename
        result["file_size"] = file.size

        # Si l'index doit être créé, proposer sa création
        if result.get("create_index"):
            corpus_id = result.get("corpus_id")
            result["index_message"] = (
                f"Un nouvel index pour le corpus {corpus_id} devrait être créé. "
                f"Utilisez l'endpoint /indexes/{corpus_id}/create pour créer l'index."
            )

        return result

    except ValueError as e:
        logger.error(f"Erreur de validation: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Erreur de validation: {str(e)}")
    except FileNotFoundError as e:
        logger.error(f"Fichier introuvable: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors du traitement: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Erreur lors du traitement: {str(e)}"
        )
    finally:
        file.file.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post(
    "/process-and-store-async",
    summary="Traiter un fichier en arrière-plan et l'insérer dans la base de données",
    response_model=Dict,
)
async def process_and_store_async_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Fichier à traiter"),
    max_length: int = Query(500, description="Taille maximale d'un chunk"),
    overlap: int = Query(100, description="Chevauchement entre les chunks"),
    theme: str = Query("Thème générique", description="Thème du document"),
    corpus_id: Optional[str] = Query(
        None, description="Identifiant du corpus (généré si non spécifié)"
    ),
):
    """Traite un fichier en arrière-plan et l'insère dans la base de données.

    Similaire à process-and-store mais s'exécute de manière asynchrone pour les fichiers
    volumineux. Le client reçoit immédiatement une réponse avec un identifiant de tâche
    pendant que le traitement se poursuit en arrière-plan.

    Args:
        background_tasks: Gestionnaire de tâches en arrière-plan de FastAPI.
        file: Fichier uploadé par l'utilisateur.
        max_length: Taille maximale d'un chunk final.
        overlap: Chevauchement entre les chunks.
        theme: Thème à appliquer au document.
        corpus_id: Identifiant du corpus (généré si non spécifié).

    Returns:
        Dict: Informations sur la tâche en arrière-plan créée.
    """
    # Sauvegarde temporaire du fichier
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename or "uploaded_file")
    file.filename = file.filename or "uploaded_file"
    try:
        with open(temp_file_path, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        # Générer un ID de tâche unique
        task_id = str(uuid.uuid4())

        # Fonction pour le traitement en arrière-plan
        def process_in_background(file_path, task_id):
            try:
                result = process_and_store(
                    file_path=file_path,
                    max_length=max_length,
                    overlap=overlap,
                    theme=theme,
                    corpus_id=corpus_id,
                )
                logger.info(
                    f"Tâche {task_id} terminée avec succès: document_id={result.get('document_id')}"
                )
                # Ici, vous pourriez stocker le résultat dans une file d'attente ou une base de données
                # pour permettre au client de récupérer les résultats ultérieurement

                # Nettoyage
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(os.path.dirname(file_path)):
                    shutil.rmtree(os.path.dirname(file_path), ignore_errors=True)
            except Exception as e:
                logger.error(f"Erreur dans la tâche {task_id}: {str(e)}", exc_info=True)

        # Ajouter la tâche en arrière-plan
        background_tasks.add_task(process_in_background, temp_file_path, task_id)

        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Le document est en cours de traitement en arrière-plan.",
            "file_name": file.filename,
            "file_size": file.size,
        }

    except Exception as e:
        # En cas d'erreur, nettoyer les fichiers temporaires
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(
            f"Erreur lors de la préparation du traitement en arrière-plan: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la préparation du traitement: {str(e)}",
        )
    finally:
        file.file.close()

