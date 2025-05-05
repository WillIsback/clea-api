import logging
import asyncio
import re
from typing import AsyncGenerator, Dict, Any, Tuple
from transformers import TextIteratorStreamer
from threading import Thread

class AsyncStreamedResponse:
    """Gestionnaire de réponses en streaming pour les interactions avec le LLM.

    Cette classe permet de gérer efficacement les réponses générées progressivement
    par le LLM et de les transmettre au client via un stream asynchrone. Elle est
    optimisée pour les modèles Qwen3 avec gestion du mode de réflexion.

    Args:
        model_loader: Chargeur de modèle LLM.
        filter_thinking: Si True, filtre le contenu de réflexion des réponses.

    Attributes:
        model_loader: Chargeur de modèle LLM.
        filter_thinking (bool): Si True, filtre le contenu de réflexion.
        logger (logging.Logger): Logger pour les messages et diagnostics.
    """

    def __init__(self, model_loader, filter_thinking: bool = False):
        """Initialise le gestionnaire de réponses en streaming.

        Args:
            model_loader: Chargeur de modèle LLM.
            filter_thinking: Si True, filtre le contenu de réflexion des réponses.
        """
        self.model_loader = model_loader
        self.filter_thinking = filter_thinking
        self.logger = logging.getLogger("clea-api.askai.streaming")

    async def generate_stream(
        self, 
        prompt: str, 
        enable_thinking: bool = True,
        chunk_size: int = 3,
        timeout: float = 60.0,
        **kwargs
    ) -> AsyncGenerator[Dict[str, str], None]:
        """Génère une réponse en streaming avec extraction du contenu thinking.

        Cette méthode utilise le TextIteratorStreamer de HuggingFace pour
        streamer les tokens générés et sépare le contenu thinking de la réponse finale.
        Chaque fragment retourné est un dictionnaire identifiant son type.

        Args:
            prompt: Texte d'entrée pour la génération.
            enable_thinking: Active le mode de réflexion du modèle.
            chunk_size: Nombre de mots par fragment (pour simulation).
            timeout: Délai maximal d'attente entre les tokens en secondes.
            **kwargs: Paramètres additionnels pour la génération.

        Yields:
            Dict[str, str]: Fragments de réponse avec leur type ('thinking' ou 'response').
        """
        try:
            # Vérification du chargeur de modèle
            if not self.model_loader or not self.model_loader.loaded:
                self.logger.error("Modèle non chargé pour le streaming")
                yield {"type": "error", "content": "Erreur: Modèle non chargé"}
                return
                       
            # Préparation du prompt selon le format de chat Qwen3
            messages = [{"role": "user", "content": prompt}]
            
            # Appliquer le template de chat avec le mode thinking approprié
            chat_text = self.model_loader.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking
            )
        
            # Tokenisation du texte d'entrée
            inputs = self.model_loader.tokenizer([chat_text], return_tensors="pt").to(self.model_loader.model.device)
            
            # Création du streamer HuggingFace
            streamer = TextIteratorStreamer(
                tokenizer=self.model_loader.tokenizer,
                skip_prompt=True,
                skip_special_tokens=True
            )
            
            # Configuration des paramètres de génération
            generation_kwargs = {
                **inputs,
                "streamer": streamer,
                "max_new_tokens": kwargs.get("max_new_tokens", 2048),
                "do_sample": kwargs.get("do_sample", True),
                "temperature": kwargs.get("temperature", 0.6),
                "top_p": kwargs.get("top_p", 0.95),
                "top_k": kwargs.get("top_k", 20),
            }

            self.logger.info("Démarrage de la génération en streaming avec séparation thinking/réponse")
            
            # Lancer la génération dans un thread séparé
            thread = Thread(target=self.model_loader.model.generate, kwargs=generation_kwargs)
            thread.daemon = True
            thread.start()
            
            # Variables pour le suivi du mode et accumulation du contenu
            in_thinking_mode = False
            thinking_content = []
            response_content = []
            current_type = "response"  # Par défaut
            
            # Traiter les tokens au fur et à mesure
            for token in streamer:
                # Détection des balises de thinking
                if "<think>" in token:
                    in_thinking_mode = True
                    current_type = "thinking"
                    # Ne pas inclure la balise dans le contenu
                    token = token.replace("<think>", "")
                    
                elif "</think>" in token:
                    in_thinking_mode = False
                    current_type = "response"
                    # Ne pas inclure la balise dans le contenu
                    token = token.replace("</think>", "")
                    # Signaler la transition
                    yield {"type": "transition", "content": ""}
                
                # Si le token contient du contenu après traitement des balises
                if token.strip():
                    # Ajouter au buffer approprié et envoyer
                    if in_thinking_mode:
                        thinking_content.append(token)
                        yield {"type": "thinking", "content": token}
                    else:
                        response_content.append(token)
                        yield {"type": "response", "content": token}
                
                # Petit délai pour éviter de surcharger la boucle asyncio
                await asyncio.sleep(0.001)

            # Fin du streaming
            yield {"type": "done", "content": ""}

        except Exception as e:
            self.logger.error(f"Erreur lors du streaming: {str(e)}")
            yield {"type": "error", "content": f"Erreur: {str(e)}"}
            
            # Tentative de fallback avec génération complète
            try:
                self.logger.info("Tentative de fallback avec génération complète")
                thinking, response = await asyncio.to_thread(
                    self.model_loader.generate_with_thinking,
                    prompt, 
                    enable_thinking=enable_thinking,
                    **kwargs
                )
                
                yield {"type": "thinking", "content": thinking}
                yield {"type": "transition", "content": ""}
                yield {"type": "response", "content": response}
                
            except Exception as fallback_error:
                self.logger.error(f"Échec du fallback: {str(fallback_error)}")