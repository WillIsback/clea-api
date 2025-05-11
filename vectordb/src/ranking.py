"""Module de reclassement des résultats de recherche basé sur un modèle Cross-Encoder."""

from typing import Sequence, List
from sentence_transformers.cross_encoder import CrossEncoder
import os
import time
from dotenv import load_dotenv
from utils import get_logger
import torch

load_dotenv()

# Configuration du logger
logger = get_logger("clea-api.vectordb.ranking")

class ResultRanker:
    """Réalise le reclassement des résultats de recherche avec un Cross-Encoder.
    
    Cette classe utilise un modèle Cross-Encoder pour évaluer la pertinence entre une requête
    et un ensemble de passages. Elle génère des scores de similarité entre chaque paire
    (requête, passage) qui permettent de trier les résultats du plus au moins pertinent.
    
    Le Cross-Encoder effectue une attention croisée entre la requête et chaque passage,
    offrant une évaluation sémantique plus précise que les embeddings traditionnels.
    """

    def __init__(self) -> None:
        """Initialise le modèle Cross-Encoder pour le reclassement.
        
        Le modèle est chargé depuis le stockage local ou depuis HuggingFace si nécessaire.
        Utilise le GPU si disponible, avec fallback automatique vers CPU en cas de problème.
        
        Args:
            Aucun
            
        Returns:
            None
            
        Raises:
            RuntimeError: Si le modèle ne peut pas être chargé après plusieurs tentatives
        """
        # Détermination dynamique du chemin absolu du dossier 'models'
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        model_path = os.path.join(project_root, "models", "reranking", "mmarco-mMiniLMv2-L12-H384-v1")
        
        # Nom du modèle, configurable via variable d'environnement
        model_name = os.getenv(
            "CROSS_ENCODER_MODEL",
            "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"  # Modèle par défaut
        )
        
        # Configuration du périphérique en fonction des priorités et disponibilités
        self._configure_device()
        
        # Chargement du modèle avec gestion des erreurs
        self.model = self._load_model_with_fallback(model_path, model_name)
        
    def _configure_device(self) -> None:
        """Configure le périphérique optimal pour le modèle en fonction de l'environnement.
        
        Prend en compte la variable d'environnement RERANKING_DEVICE et la disponibilité du GPU.
        
        Args:
            Aucun
            
        Returns:
            None
        """
        # Récupérer la configuration du périphérique depuis les variables d'environnement
        reranking_device = os.getenv("RERANKING_DEVICE", "auto")
        
        # Vérifier la disponibilité du GPU
        gpu_available = torch.cuda.is_available()
        gpu_memory_info = None
        
        # Si GPU disponible, obtenir les infos de mémoire
        if gpu_available:
            try:
                # Vérifier la mémoire disponible sur le GPU
                gpu_memory_info = torch.cuda.get_device_properties(0).total_memory
                free_memory = torch.cuda.memory_reserved(0) - torch.cuda.memory_allocated(0)
                logger.debug(f"Mémoire GPU totale: {gpu_memory_info / 1e9:.2f} GB, "
                           f"disponible: {free_memory / 1e9:.2f} GB")
            except Exception as e:
                logger.warning(f"Impossible d'obtenir les informations sur la mémoire GPU: {e}")
                gpu_memory_info = None
                
        # Déterminer le périphérique à utiliser
        if reranking_device == "cpu":
            # Forcer l'utilisation du CPU si configuré explicitement
            self.device = "cpu"
            logger.info("Reranking forcé sur CPU par configuration")
        elif reranking_device == "cuda" and gpu_available:
            # Utiliser le GPU si demandé et disponible
            self.device = "cuda"
            logger.info("Reranking sur GPU (CUDA) comme configuré")
        elif reranking_device == "auto":
            # Mode automatique: GPU si disponible, sinon CPU
            if gpu_available:
                self.device = "cuda"
                logger.info("Reranking sur GPU (détection automatique)")
            else:
                self.device = "cpu"
                logger.info("Reranking sur CPU (détection automatique, GPU non disponible)")
        else:
            # Par défaut, utiliser le CPU
            self.device = "cpu"
            logger.info(f"Reranking sur CPU (configuration non reconnue: {reranking_device})")
            
    def _load_model_with_fallback(self, local_path: str, hf_model_name: str) -> CrossEncoder:
        """Charge le modèle Cross-Encoder avec différentes stratégies et gestion d'erreurs.
        
        Tente plusieurs approches de chargement dans cet ordre:
        1. Chargement depuis le chemin local
        2. Chargement depuis Hugging Face avec périphérique spécifié
        3. Chargement avec to_empty() pour gérer les tenseurs meta
        4. Fallback vers CPU si nécessaire
        
        Args:
            local_path: Chemin local où le modèle pourrait être stocké
            hf_model_name: Nom du modèle sur Hugging Face
            
        Returns:
            CrossEncoder: Instance du modèle chargé
            
        Raises:
            RuntimeError: Si toutes les tentatives de chargement échouent
        """
        strategies = [
            # Stratégie 1: Modèle local
            {
                "desc": f"modèle local sur {self.device}",
                "loader": lambda: self._load_local_model(local_path),
            },
            # Stratégie 2: Modèle Hugging Face direct
            {
                "desc": f"modèle Hugging Face sur {self.device}",
                "loader": lambda: self._load_hf_model(hf_model_name),
            },
            # Stratégie 3: Modèle Hugging Face avec to_empty (pour les tenseurs meta)
            {
                "desc": f"modèle Hugging Face avec to_empty() sur {self.device}",
                "loader": lambda: self._load_hf_model_with_empty(hf_model_name),
            },
            # Stratégie 4: Fallback CPU
            {
                "desc": "modèle sur CPU (fallback)",
                "loader": lambda: self._load_cpu_fallback(hf_model_name),
            },
        ]
        
        # Essayer chaque stratégie jusqu'à ce qu'une fonctionne
        for strategy in strategies:
            try:
                logger.debug(f"Tentative de chargement: {strategy['desc']}")
                model = strategy["loader"]()
                logger.info(f"✅ Modèle Cross-Encoder chargé avec succès via {strategy['desc']}")
                return model
            except Exception as e:
                logger.warning(f"❌ Échec du chargement via {strategy['desc']}: {str(e)}")
                continue
                
        # Si toutes les stratégies échouent
        raise RuntimeError("Impossible de charger le modèle Cross-Encoder par aucune méthode")
            
    def _load_local_model(self, path: str) -> CrossEncoder:
        """Charge le modèle à partir du chemin local avec les configurations optimales.
        
        Args:
            path: Chemin local vers le modèle
            
        Returns:
            CrossEncoder: Instance du modèle chargé
            
        Raises:
            ValueError: Si le chemin n'existe pas ou est invalide
        """
        if not os.path.exists(path):
            raise ValueError(f"Le chemin local {path} n'existe pas")
            
        return CrossEncoder(path, device=self.device, model_kwargs={
            "torch_dtype": torch.float32 if self.device == "cpu" else torch.float16
        })
    
    def _load_hf_model(self, model_name: str) -> CrossEncoder:
        """Charge le modèle depuis Hugging Face avec le périphérique configuré.
        
        Args:
            model_name: Nom du modèle sur Hugging Face
            
        Returns:
            CrossEncoder: Instance du modèle chargé
        """
        return CrossEncoder(model_name, device=self.device)
        
    def _load_hf_model_with_empty(self, model_name: str) -> CrossEncoder:
        """Charge le modèle avec la méthode to_empty pour gérer les tenseurs meta.
        
        Args:
            model_name: Nom du modèle sur Hugging Face
            
        Returns:
            CrossEncoder: Instance du modèle chargé
        """
        model = CrossEncoder(model_name)
        return model.to_empty(device=self.device)
        
    def _load_cpu_fallback(self, model_name: str) -> CrossEncoder:
        """Charge le modèle en mode CPU comme dernière option.
        
        Args:
            model_name: Nom du modèle sur Hugging Face
            
        Returns:
            CrossEncoder: Instance du modèle chargé
        """
        previous_device = self.device
        self.device = "cpu"
        logger.warning(f"Fallback du périphérique {previous_device} vers CPU")
        return CrossEncoder(model_name, device="cpu")

    def rank_results(self, query: str, texts: Sequence[str]) -> List[float]:
        """Évalue la pertinence entre la requête et chaque texte fourni.
        
        Cette méthode calcule un score de similarité pour chaque paire (requête, texte)
        en utilisant le modèle Cross-Encoder. Les scores plus élevés indiquent une plus
        grande pertinence sémantique.
        
        Args:
            query: Requête ou question de l'utilisateur.
            texts: Séquence de textes à évaluer (passages de documents).
            
        Returns:
            Liste de scores de similarité (valeurs flottantes) dans le même ordre que les textes d'entrée.
            Les scores sont généralement compris entre -10 et 10 (non normalisés).
        """
        # Vérifier si nous avons des textes à évaluer
        if not texts:
            logger.warning("Aucun texte fourni pour le reclassement")
            return []
            
        # Création des paires (requête, texte) pour chaque texte
        pairs = [(query, text) for text in texts]
        
        # Mesure du temps d'exécution pour les performances
        start_time = time.time()
        
        try:
            # Prédiction avec le Cross-Encoder
            scores = self.model.predict(pairs, show_progress_bar=False)
            
            # Log des performances
            duration = time.time() - start_time
            logger.debug(f"Reclassement de {len(texts)} textes en {duration:.3f}s "
                        f"({len(texts)/duration:.1f} textes/sec) sur {self.device}")
                
            return scores
            
        except Exception as e:
            logger.error(f"Erreur lors du reclassement: {e}")
            # En cas d'erreur, retourner des scores neutres
            return [0.0] * len(texts)
    
if __name__ == "__main__":
    # Exemple d'utilisation
    query = "Quel est le capital de la France ?"
    texts = [
        "La France est un pays d'Europe.",
        "Paris est la capitale de la France.",
        "Le Louvre est un musée célèbre à Paris.",
        ",vksd,vkdsdé",
        "How are you today"
    ]
    ranker = ResultRanker()
    scores = ranker.rank_results(query, texts)
    
    print("Scores de pertinence :", scores)
    scored_results = list(zip(texts, scores))
    print("Résultats classés :", sorted(scored_results, key=lambda x: x[1], reverse=True))