import logging
from typing import Optional, Tuple
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM  # type: ignore


class ModelLoader:
    """Chargeur de modèle LLM pour la génération de réponses.
    
    Cette classe gère le chargement et la configuration des modèles Qwen3
    optimisés pour un usage RAG avec des ressources limitées. Elle utilise
    prioritairement les modèles disponibles localement dans `askai/models/`.
    
    Args:
        model_name: Nom du modèle à charger (défaut: "Qwen/Qwen3-0.6B").
        device: Périphérique de calcul; si None, utilise cuda si disponible, sinon cpu.
        load_in_8bit: Active la quantification 8-bit pour économiser la mémoire.
        base_path: Chemin de base vers le répertoire des modèles.
        thinking_enabled: Active le mode de réflexion par défaut.
        auto_load: Charge automatiquement le modèle lors de l'initialisation.
        test_mode: Active le mode test qui simule les réponses sans charger de modèle.
        auto_fix: Tente de réparer automatiquement les problèmes de tokenizer.
        
    Attributes:
        model_name: Nom du modèle à charger.
        device: Périphérique de calcul ('cpu', 'cuda', 'mps', 'auto').
        load_in_8bit: Activation de la quantification 8-bit.
        base_path: Chemin de base vers le répertoire des modèles.
        model: Instance du modèle chargé.
        tokenizer: Tokenizer associé au modèle.
        max_context_length: Longueur maximale du contexte supportée par le modèle.
        thinking_enabled: État d'activation du mode de réflexion par défaut.
        loaded: Indique si le modèle est chargé.
        test_mode: Indique si le mode test est actif.
        auto_fix: Indique si la réparation automatique est activée.
        logger: Logger pour les messages et diagnostics.
    """

    # Modèles supportés avec leurs configurations par défaut
    SUPPORTED_MODELS = {
        "Qwen/Qwen3-0.6B": {
            "max_context_length": 32768,
            "thinking_enabled": True,
            "dependencies": ["protobuf", "tokenizers>=0.13.3"]
        },
        "Qwen/Qwen3-1.7B": {
            "max_context_length": 32768,
            "thinking_enabled": True,
            "dependencies": ["protobuf", "tokenizers>=0.13.3"]
        }
    }

    def __init__(
        self, 
        model_name: str = "Qwen/Qwen3-0.6B", 
        device: Optional[str] = None,
        load_in_8bit: bool = False,
        base_path: str = "askai/models",
        thinking_enabled: bool = True,
        auto_load: bool = False,
        test_mode: bool = False,
        auto_fix: bool = True
    ):
        """Initialise le chargeur de modèle.
        
        Args:
            model_name: Nom du modèle à charger (défaut: "Qwen/Qwen3-0.6B").
            device: Périphérique de calcul ('cpu', 'cuda', 'mps', 'auto').
            load_in_8bit: Active la quantification 8-bit pour économiser la mémoire.
            base_path: Chemin de base vers le répertoire des modèles.
            thinking_enabled: Active le mode de réflexion par défaut.
            auto_load: Charge automatiquement le modèle lors de l'initialisation.
            test_mode: Active le mode test qui simule les réponses sans charger de modèle.
            auto_fix: Tente de réparer automatiquement les problèmes de tokenizer.
        """
        self.logger = logging.getLogger("clea-api.askai.model_loader")
        self.model_name = model_name
        self.base_path = base_path
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.load_in_8bit = load_in_8bit
        self.model = None
        self.tokenizer = None
        self.loaded = False
        self.test_mode = test_mode
        self.auto_fix = auto_fix
        
            
        model_config = self.SUPPORTED_MODELS.get(model_name, {})
        self.max_context_length = model_config.get("max_context_length", 32768)
        self.thinking_enabled = thinking_enabled
        
        self.logger.info(f"Initialisation du modèle {model_name} sur {self.device} (test_mode={test_mode})")
        
        # En mode test, marquer immédiatement comme chargé
        if test_mode:
            self.loaded = True
            self.logger.info("Mode test activé, modèle marqué comme chargé")
        # Sinon, chargement automatique du modèle si demandé
        elif auto_load:
            self.load()
    
    def get_model_list(self) -> list:
        """Retourne la liste des modèles supportés.
        
        Returns:
            list: Liste des noms de modèles supportés.
        """
        return list(self.SUPPORTED_MODELS.keys())



    def load(self) -> None:
        """Charge le modèle et le tokenizer en mémoire.
        
        Optimise la configuration selon les capacités du système et les besoins de l'application RAG.
        Si le modèle est disponible localement dans le répertoire askai/models/, il est chargé
        depuis ce chemin, sinon une tentative de téléchargement depuis HuggingFace est effectuée.
        
        Raises:
            RuntimeError: Si le chargement du modèle échoue.
        """
        if self.test_mode:
            self.logger.info("Mode test activé, aucun modèle ne sera chargé")
            self.loaded = True
            return
            
        try:           

            self.logger.info(f"Chargement du modèle depuis: {self.model_name}")
            
            # load the tokenizer and the model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype="auto",
                device_map="auto"
            )

            self.loaded = True
            self.logger.info(f"Modèle {self.model_name} chargé avec succès")

        except Exception as e:
            self.logger.error(f"Erreur lors du chargement du modèle: {str(e)}")
        
            raise RuntimeError(str(e))
        
    def generate(
        self, 
        prompt: str, 
        enable_thinking: bool = True,
        max_new_tokens: int = 2048,
        do_sample: bool = True,
        temperature: float = 0.6,
        top_p: float = 0.95,
        top_k: int = 20,
        return_thinking: bool = False,
        **kwargs
    ) -> str:
        """Génère du texte à partir d'un prompt donné.
        
        Cette méthode utilise le modèle Qwen pour générer une réponse
        à partir du prompt, avec gestion spécifique du mode thinking.
        
        Args:
            prompt: Texte d'entrée pour la génération.
            enable_thinking: Active le mode thinking.
            max_new_tokens: Nombre maximum de tokens à générer.
            do_sample: Utilise l'échantillonnage au lieu du greedy decoding.
            temperature: Contrôle la créativité (plus élevé = plus aléatoire).
            top_p: Filtrage nucleus sampling (0-1).
            top_k: Nombre de tokens considérés à chaque étape.
            return_thinking: Si True, retourne uniquement la partie thinking.
            **kwargs: Paramètres supplémentaires pour la génération.
            
        Returns:
            str: Texte généré (réponse ou thinking selon return_thinking).
            
        Raises:
            RuntimeError: Si le modèle n'est pas chargé.
        """
        thinking, response = self.generate_with_thinking(
            prompt=prompt,
            enable_thinking=enable_thinking,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            **kwargs
        )
        
        if enable_thinking:
            return thinking, response
        else:
            return response
        
        
    def generate_with_thinking(
        self, 
        prompt: str, 
        enable_thinking: bool = True,
        max_new_tokens: int = 2048,
        do_sample: bool = True,
        temperature: float = 0.6,
        top_p: float = 0.95,
        top_k: int = 20,
        **kwargs
    ) -> Tuple[str, str]:
        """Génère du texte à partir d'un prompt avec séparation du thinking et de la réponse.
        
        Cette méthode utilise le modèle pour générer une réponse et sépare
        la partie thinking de la réponse finale.
        
        Args:
            prompt: Texte d'entrée pour la génération.
            enable_thinking: Active le mode thinking.
            max_new_tokens: Nombre maximum de tokens à générer.
            do_sample: Utilise l'échantillonnage au lieu du greedy decoding.
            temperature: Contrôle la créativité (plus élevé = plus aléatoire).
            top_p: Filtrage nucleus sampling (0-1).
            top_k: Nombre de tokens considérés à chaque étape.
            **kwargs: Paramètres supplémentaires pour la génération.
            
        Returns:
            Tuple[str, str]: Tuple contenant (contenu_thinking, réponse_finale).
            
        Raises:
            RuntimeError: Si le modèle n'est pas chargé.
        """
        # Mode test pour les environnements sans GPU ou les tests
        if self.test_mode:
            if "Aucun résultat pertinent" in prompt:
                return "", "Aucune information pertinente n'a été trouvée pour votre requête."
            elif enable_thinking:
                return "Je dois répondre à la question en utilisant le contexte fourni.", "Voici une réponse simulée avec thinking mode activé."
            else:
                return "", "Réponse standard."
        
        # Vérifier si le modèle est chargé
        if not self.loaded or not self.model or not self.tokenizer:
            self.logger.error("Tentative de génération sans modèle chargé")
            raise RuntimeError("Le modèle n'est pas chargé. Veuillez appeler load() avant de générer.")
        
        # Préparation du prompt selon le format de chat Qwen3
        messages = [{"role": "user", "content": prompt}]
        
        # Appliquer le template de chat avec le mode thinking approprié
        chat_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking
        )
        
        # Tokeniser le texte
        inputs = self.tokenizer([chat_text], return_tensors="pt").to(self.model.device)
        
        # Paramètres de génération
        generation_config = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            **kwargs
        }
        
        # Génération du texte
        self.logger.debug(f"Génération avec paramètres: {generation_config}")
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                **generation_config
            )
        
        # Extraction du texte généré (en excluant le prompt d'entrée)
        generated_ids = output_ids[0][len(inputs.input_ids[0]):].tolist()
        
        # Extraction du contenu thinking et de la réponse finale
        try:
            # Trouver l'index de </think> (token 151668)
            think_end_token = 151668
            index = len(generated_ids) - generated_ids[::-1].index(think_end_token)
            
            # Séparer le thinking du contenu final
            thinking_content = self.tokenizer.decode(generated_ids[:index], skip_special_tokens=True).strip("\n")
            content = self.tokenizer.decode(generated_ids[index:], skip_special_tokens=True).strip("\n")
            
            self.logger.debug(f"Thinking extrait: {thinking_content[:100]}...")
            self.logger.debug(f"Contenu final extrait: {content[:100]}...")
            
            # Retourner le tuple (thinking, réponse)
            return thinking_content, content
        
        except (ValueError, IndexError):
            # Si pas de balise </think>, retourner tout comme réponse sans thinking
            full_response = self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip("\n")
            self.logger.debug("Pas de thinking détecté, retour de la réponse complète")
            return "", full_response