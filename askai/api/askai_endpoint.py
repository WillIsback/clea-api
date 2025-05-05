from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
import logging
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
import json
from datetime import date, datetime

from ..src.model_loader import ModelLoader
from ..src.rag import RAGProcessor
from vectordb.src.search import SearchEngine
from vectordb.src.database import get_db

# ──────────────────────────────────────────────────────────────
router = APIRouter()
# ──────────────────────────────────────────────────────────────
# Helpers & global Config
# ──────────────────────────────────────────────────────────────
def _to_camel(s: str) -> str:
    head, *tail = s.split("_")
    return head + "".join(word.capitalize() for word in tail)


CamelConfig: ConfigDict = {
    "alias_generator": _to_camel,
    "populate_by_name": True,  # accepte les deux formes en entrée
}

# Instance partagée du modèle (lazy loading)
model_loader = None
# Instance partagée du moteur de recherche
search_engine = None

def get_search_engine() -> SearchEngine:
    """Récupère l'instance du moteur de recherche, l'initialise si nécessaire.
    
    Returns:
        SearchEngine: Instance du moteur de recherche.
    """
    global search_engine
    if search_engine is None:
        search_engine = SearchEngine()
    return search_engine

# ──────────────────────────────────────────────────────────────
# Schémas de requête
class AskRequest(BaseModel):
    """Requête pour poser une question au système RAG.
    
    Args:
        query: Question à poser au système.
        filters: Filtres pour la recherche documentaire.
        theme: Thème pour filtrer les documents.
        model_name: Nom du modèle à utiliser.
        stream: Indique si la réponse doit être streamée.
        prompt_type: Type de prompt à utiliser.
    
    Attributes:
        query (str): Question ou requête de l'utilisateur.
        filters (Optional[Dict[str, Any]]): Filtres pour la recherche documentaire.
        theme (Optional[str]): Thème pour filtrer les documents.
        model_name (Optional[str]): Nom du modèle à utiliser.
        stream (bool): Indique si la réponse doit être streamée.
        prompt_type (str): Type de prompt à utiliser ('standard', 'summary', 'comparison').
    """
    query: str = Field(..., description="Question à poser au système")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Filtres pour la recherche"
    )
    theme: Optional[str] = Field(None, description="Thème pour filtrer les documents")
    model_name: Optional[str] = Field(
        "Qwen3-0.6B", description="Modèle à utiliser"
    )
    stream: bool = Field(False, description="Réponse en streaming")
    prompt_type: str = Field("standard", description="Type de prompt (standard, summary, comparison)")
    enable_thinking: bool = Field(False, description="Activer le mode 'think' pour le modèle")
    
    model_config = CamelConfig


# ──────────────────────────────────────────────────────────────
# Encodeur JSON personnalisé pour les types non-sérialisables
# ──────────────────────────────────────────────────────────────
class CustomJSONEncoder(json.JSONEncoder):
    """Encodeur JSON personnalisé pour gérer les types non-sérialisables nativement.
    
    Cet encodeur étend la classe JSONEncoder standard pour prendre en charge 
    des types spécifiques comme datetime, date, et d'autres objets personnalisés.
    
    Attributes:
        default_format (str): Format de date par défaut (ISO8601).
    """

    default_format = "%Y-%m-%d"  # Format ISO8601
    
    def default(self, obj):
        """Convertit des objets spécifiques en types JSON sérialisables.
        
        Args:
            obj: L'objet à sérialiser en JSON.
            
        Returns:
            Une représentation sérialisable de l'objet.
            
        Raises:
            TypeError: Si l'objet ne peut pas être sérialisé.
        """
        if isinstance(obj, (datetime, date)):
            return obj.strftime(self.default_format)
        elif hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
            # Gestion des objets Pydantic ou avec une méthode dict()
            return obj.dict()
        elif hasattr(obj, '__dict__'):
            # Fallback pour les objets personnalisés
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        # Laisser l'encodeur par défaut gérer les autres types
        return super().default(obj)

def json_serialize(obj):
    """Sérialise un objet en JSON en gérant les types spéciaux.
    
    Args:
        obj: L'objet à sérialiser.
        
    Returns:
        str: Représentation JSON de l'objet.
    """
    return json.dumps(obj, cls=CustomJSONEncoder, ensure_ascii=False)

# ──────────────────────────────────────────────────────────────
# Le reste du code...

@router.post("/ask")
async def ask_ai(
    request: AskRequest = Body(...),
    db: Session = Depends(get_db),
    search_engine: SearchEngine = Depends(get_search_engine)
):
    """Endpoint pour poser une question et obtenir une réponse basée sur les documents.
    
    Cette fonction interroge la base documentaire avec la question fournie,
    récupère les documents pertinents et utilise un modèle LLM pour générer
    une réponse contextuelle.
    
    Args:
        request: Paramètres de la requête (query, filters, etc.).
        db: Session de base de données SQLAlchemy.
        search_engine: Instance du moteur de recherche vectorielle.
        
    Returns:
        Dict[str, Any] ou StreamingResponse: Réponse générée avec contexte.
            
    Raises:
        HTTPException: Si une erreur survient lors du traitement.
    """
    try:
        # Préparation des filtres
        filters = request.filters or {}
        if request.theme:
            filters["theme"] = request.theme

        loader = ModelLoader(
            model_name=request.model_name)
        if not loader.loaded:
            loader.load()

        # Initialisation du processeur RAG
        processor = RAGProcessor(
            model_loader=loader, 
            search_engine=search_engine, 
            db_session=db
        )

        if request.stream:
            # Streaming de la réponse
            async def stream_generator():
                async for chunk in processor.retrieve_and_generate_stream(
                    query=request.query, 
                    filters=filters,
                    prompt_type=request.prompt_type,
                    enable_thinking=request.enable_thinking
                ):
                    # Format JSON pour chaque chunk avec son type
                    # Utiliser l'encodeur personnalisé pour gérer les dates et autres types
                    yield f"data: {json_serialize(chunk)}\n\n"
                
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_generator(), 
                media_type="text/event-stream"
            )
        else:
            # Réponse standard (non streamée)
            if request.enable_thinking:
                thinking, response, search_results = await processor.retrieve_and_generate(
                    query=request.query,
                    filters=filters,
                    prompt_type=request.prompt_type,
                    enable_thinking=True
                )
                return {
                    "response": response,
                    "thinking": thinking,
                    "context": search_results
                }
            else:
                response, search_results = await processor.retrieve_and_generate(
                    query=request.query,
                    filters=filters,
                    prompt_type=request.prompt_type,
                    enable_thinking=False
                )
                return {
                    "response": response,
                    "context": search_results
                }

    except Exception as e:
        logger = logging.getLogger("clea-api.askai.endpoint")
        logger.error(f"Erreur lors du traitement de la demande: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/models")
async def get_models():
    """Endpoint pour récupérer la liste des modèles disponibles.
    
    Returns:
        List[str]: Liste des noms de modèles disponibles.
    """
    try:
        # Récupération de la liste des modèles
        model_loader = ModelLoader()
        models = model_loader.get_model_list()
        return {"models": models}
    except Exception as e:
        logger = logging.getLogger("clea-api.askai.endpoint")
        logger.error(f"Erreur lors de la récupération des modèles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


