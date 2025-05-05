import logging
from typing import Dict, Any, Optional, AsyncGenerator

from sqlalchemy.orm import Session

from .model_loader import ModelLoader
from .prompt_schemas import StandardRAGPrompt, SummaryRAGPrompt, ComparisonRAGPrompt, PromptTemplate
from .async_streamed_response import AsyncStreamedResponse
from vectordb.src.schemas import SearchResponse, SearchRequest
from vectordb.src.search import SearchEngine
import asyncio

class RAGProcessor:
    """Processeur RAG (Retrieval-Augmented Generation) optimisé pour petits LLM.
    
    Cette classe orchestre la récupération de documents pertinents et leur
    utilisation pour générer des réponses avec un petit modèle LLM Qwen3.
    
    Args:
        model_loader: Chargeur de modèle LLM.
        search_engine: Moteur de recherche vectorielle.
        db_session: Session de base de données SQLAlchemy.
        max_tokens_per_doc: Nombre maximum de tokens par document.
        max_docs: Nombre maximum de documents à utiliser.
    
    Attributes:
        model_loader (ModelLoader): Chargeur de modèle LLM.
        search_engine (SearchEngine): Moteur de recherche vectorielle.
        db_session (Session): Session de base de données SQLAlchemy.
        max_tokens_per_doc (int): Nombre maximum de tokens par document.
        max_docs (int): Nombre maximum de documents à utiliser.
        logger (logging.Logger): Logger pour les messages et diagnostics.
    """
    
    def __init__(
        self,
        model_loader: ModelLoader,
        search_engine: SearchEngine,
        db_session: Session,
        max_tokens_per_doc: int = 300,
        max_docs: int = 5,
    ):
        """Initialise le processeur RAG.
        
        Args:
            model_loader: Chargeur de modèle LLM.
            search_engine: Moteur de recherche vectorielle.
            db_session: Session de base de données SQLAlchemy.
            max_tokens_per_doc: Nombre maximum de tokens par document.
            max_docs: Nombre maximum de documents à utiliser.
        """
        self.model_loader = model_loader
        self.search_engine = search_engine
        self.db_session = db_session
        self.max_tokens_per_doc = max_tokens_per_doc
        self.max_docs = max_docs
        self.logger = logging.getLogger("clea-api.askai.rag")

    def format_context(self, search_results: SearchResponse) -> str:
        """Formate les résultats de recherche en contexte structuré pour le LLM.
        
        Utilise les résultats d'une requête pour créer un contexte formaté
        qui sera utilisé dans le prompt envoyé au modèle LLM.
        
        Args:
            search_results: Réponse de recherche contenant les chunks pertinents.
            
        Returns:
            str: Contexte formaté prêt à être injecté dans le prompt.
        """
        formatted_docs = []

        for i, result in enumerate(search_results.results):
            # Formatage clair et structuré pour faciliter le traitement par le LLM
            doc_text = f"DOCUMENT {i + 1}:\n"
            doc_text += f"TITRE: {result.title}\n"
            doc_text += f"SOURCE: {result.document_type}\n"
            doc_text += f"THÈME: {result.theme}\n"
            doc_text += f"DATE: {result.publish_date.strftime('%d/%m/%Y')}\n"
            
            # Ajout du contexte hiérarchique s'il est disponible
            if result.context:
                if result.context.level_0:
                    doc_text += f"SECTION: {result.context.level_0.get('content', '').strip()[:100]}...\n"
                if result.context.level_1:
                    doc_text += f"SOUS-SECTION: {result.context.level_1.get('content', '').strip()[:100]}...\n"
                
            doc_text += f"PERTINENCE: {result.score:.2f}\n"
            doc_text += f"CONTENU:\n{result.content}\n"

            formatted_docs.append(doc_text)

        return "\n---\n".join(formatted_docs)

    def get_prompt_template(
        self, query: str, context: str, prompt_type: str = "standard", **kwargs
    ) -> PromptTemplate:
        """Retourne un template de prompt adapté au type de requête.
        
        Args:
            query: Question de l'utilisateur.
            context: Contexte documentaire formaté.
            prompt_type: Type de prompt à utiliser ('standard', 'summary', 'comparison').
            **kwargs: Paramètres additionnels spécifiques au type de prompt.
            
        Returns:
            PromptTemplate: Template de prompt configuré avec les variables appropriées.
            
        Raises:
            ValueError: Si le type de prompt spécifié n'est pas reconnu.
        """
        variables = {"query": query, "context": context, **kwargs}
        
        if prompt_type == "standard":
            return StandardRAGPrompt(variables=variables)
        elif prompt_type == "summary":
            # S'assurer que target_length est défini pour les résumés
            if "target_length" not in variables:
                variables["target_length"] = 200
            return SummaryRAGPrompt(variables=variables)
        elif prompt_type == "comparison":
            return ComparisonRAGPrompt(variables=variables)
        else:
            raise ValueError(f"Type de prompt non reconnu: {prompt_type}")

    async def retrieve_documents(self, query: str, filters: Dict[str, Any] = None) -> SearchResponse:
        """Récupère les documents pertinents pour une requête donnée.
        
        Effectue une recherche dans la base de données vectorielle et retourne
        les résultats formatés selon le schéma standard de l'application.
        
        Args:
            query: Question de l'utilisateur.
            filters: Filtres à appliquer lors de la recherche.
                
        Returns:
            SearchResponse: Réponse contenant les résultats de recherche pertinents.
        """
        # Initialisation des filtres par défaut
        filters = filters or {}
        
        # Construction de la requête de recherche
        search_request = SearchRequest(
            query=query,
            top_k=self.max_docs,
            theme=filters.get("theme"),
            document_type=filters.get("document_type"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            corpus_id=filters.get("corpus_id"),
            hierarchy_level=filters.get("hierarchy_level"),
            hierarchical=True,  # Toujours récupérer le contexte hiérarchique
            filter_by_relevance=filters.get("filter_by_relevance", False),
            normalize_scores=filters.get("normalize_scores", True),
        )
        
        # Exécution de la recherche
        search_results = self.search_engine.hybrid_search(self.db_session, search_request)
        
        self.logger.info(f"Récupéré {len(search_results.results)} documents pertinents")
        return search_results

    async def retrieve_and_generate(
        self, 
        query: str, 
        filters: Dict[str, Any] = None,
        prompt_type: str = "standard",
        generation_kwargs: Dict[str, Any] = None,
        enable_thinking: Optional[bool] = None,
        **prompt_kwargs
    ) -> tuple:
        """Récupère les documents pertinents et génère une réponse.
        
        Args:
            query: Question de l'utilisateur.
            filters: Filtres à appliquer lors de la recherche.
            prompt_type: Type de prompt à utiliser ('standard', 'summary', 'comparison').
            generation_kwargs: Paramètres additionnels pour la génération de texte.
            enable_thinking: Active ou désactive le mode de réflexion. Si None, utilise la configuration du modèle.
            **prompt_kwargs: Paramètres additionnels pour le template de prompt.
            
        Returns:
            tuple: 
                - Si enable_thinking=True : (thinking, response, search_results)
                - Si enable_thinking=False : (response, search_results)
        """
        
        # Paramètres par défaut pour la génération optimisés pour Qwen3
        generation_params = {
            "enable_thinking": enable_thinking,
            "max_new_tokens": 2048,  # Valeur par défaut raisonnable, Qwen3 supporte jusqu'à 32K tokens
            "do_sample": True,       # Éviter le greedy decoding comme recommandé par Qwen
        }
        
        # Paramètres spécifiques selon le mode de réflexion
        if enable_thinking:
            # Paramètres recommandés pour le mode thinking
            generation_params.update({
                "temperature": 0.6,
                "top_p": 0.95,
                "top_k": 20,
            })
            self.logger.debug("Utilisation des paramètres pour le mode thinking")
        else:
            # Paramètres recommandés pour le mode non-thinking
            generation_params.update({
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 20,
            })
            self.logger.debug("Utilisation des paramètres pour le mode non-thinking")
        
        # Mise à jour avec les paramètres fournis par l'utilisateur
        if generation_kwargs:
            generation_params.update(generation_kwargs)
        
        # 1. Récupération des documents
        search_results = await self.retrieve_documents(query, filters)

        if not search_results.results:
            if enable_thinking:
                return "", "Aucune information pertinente n'a été trouvée pour répondre à cette question.", search_results
            else:
                return "Aucune information pertinente n'a été trouvée pour répondre à cette question.", search_results

        # 2. Formatage du contexte
        context = self.format_context(search_results)

        # 3. Création du prompt en utilisant le template approprié
        prompt_template = self.get_prompt_template(
            query=query, 
            context=context, 
            prompt_type=prompt_type,
            **prompt_kwargs
        )
        
        prompt = prompt_template.format()
        self.logger.debug(f"Prompt généré: {prompt[:100]}...")

        # 4. Génération de la réponse
        self.logger.info(f"Génération de la réponse avec {prompt_type=}, thinking={enable_thinking}")
        if enable_thinking:
            thinking, response = self.model_loader.generate_with_thinking(prompt=prompt, **generation_params)
            return thinking, response, search_results
        else:
            response = self.model_loader.generate(prompt=prompt, **generation_params)
            return response, search_results

    async def retrieve_and_generate_stream(
        self,
        query: str,
        filters: Dict[str, Any] = None,
        prompt_type: str = "standard",
        generation_kwargs: Dict[str, Any] = None,
        enable_thinking: Optional[bool] = None,
        **prompt_kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Récupère les documents pertinents et génère une réponse en streaming.
        
        Cette méthode enrichit la réponse avec les documents utilisés pour la génération.
        Chaque fragment retourné est un dictionnaire identifiant son type et contenu.
        
        Args:
            query: Question de l'utilisateur.
            filters: Filtres à appliquer lors de la recherche.
            prompt_type: Type de prompt à utiliser ('standard', 'summary', 'comparison').
            generation_kwargs: Paramètres additionnels pour la génération de texte.
            enable_thinking: Active ou désactive le mode de réflexion. Si None, utilise la configuration du modèle.
            **prompt_kwargs: Paramètres additionnels pour le template de prompt.
            
        Yields:
            Dict[str, Any]: Fragments de la réponse ou métadonnées avec leur type :
                - {"type": "thinking", "content": str} pour les parties de réflexion
                - {"type": "response", "content": str} pour les parties de réponse
                - {"type": "context", "content": Dict} pour le contexte utilisé
                - {"type": "error", "content": str} en cas d'erreur
                - {"type": "done", "content": ""} à la fin du streaming
        """
        try:
            # Déterminer si le mode de réflexion est activé de façon sécurisée
            use_thinking = True  # Valeur par défaut
            if enable_thinking is not None:
                # Si explicitement fourni, utiliser cette valeur
                use_thinking = enable_thinking
            elif hasattr(self.model_loader, 'thinking_enabled') and self.model_loader.thinking_enabled is not None:
                # Sinon utiliser la configuration du modèle si disponible
                use_thinking = self.model_loader.thinking_enabled
            
            # Paramètres de génération par défaut pour le streaming
            generation_params = {
                "enable_thinking": use_thinking,
                "max_new_tokens": 2048,
                "do_sample": True,
                "temperature": 0.6,
                "top_p": 0.95,
                "top_k": 20,
            }
            
            # Mettre à jour avec les paramètres fournis, s'il y en a
            if generation_kwargs is not None:
                generation_params.update(generation_kwargs)
            
            # En mode test, simuler une réponse simple avec contexte
            if hasattr(self.model_loader, 'test_mode') and self.model_loader.test_mode:
                yield {"type": "context", "content": {"results": [{"title": "Document test", "content": "Contenu test"}]}}
                yield {"type": "response", "content": "Partie 1 de la réponse en streaming."}
                await asyncio.sleep(0.01)
                yield {"type": "response", "content": "Partie 2 de la réponse en streaming."}
                await asyncio.sleep(0.01)
                yield {"type": "response", "content": "Partie 3 de la réponse en streaming."}
                yield {"type": "done", "content": ""}
                return
                    
            # 1. Récupération des documents
            search_results = await self.retrieve_documents(query, filters)

            # Transmettre immédiatement le contexte en premier fragment
            yield {"type": "context", "content": search_results.dict()}

            if not search_results.results:
                yield {"type": "response", "content": "Aucune information pertinente n'a été trouvée pour répondre à cette question."}
                yield {"type": "done", "content": ""}
                return

            # 2. Formatage du contexte
            context = self.format_context(search_results)

            # 3. Création du prompt en utilisant le template approprié
            prompt_template = self.get_prompt_template(
                query=query,
                context=context,
                prompt_type=prompt_type,
                **prompt_kwargs
            )
            
            prompt = prompt_template.format()
            self.logger.debug(f"Prompt de streaming généré: {prompt[:100]}...")
            
            # 4. Initialisation du gestionnaire de streaming
            streamer = AsyncStreamedResponse(self.model_loader)
            
            # 5. Génération et streaming de la réponse
            async for chunk in streamer.generate_stream(prompt, **generation_params):
                yield chunk

            # Marquer la fin du streaming
            yield {"type": "done", "content": ""}

        except Exception as e:
            self.logger.error(f"Erreur lors de la génération en streaming: {str(e)}")
            yield {"type": "error", "content": f"Erreur pendant la génération: {str(e)}"}