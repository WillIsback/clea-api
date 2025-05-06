"""Module de reclassement des résultats de recherche basé sur un modèle Cross-Encoder."""

from typing import Sequence, List
from sentence_transformers.cross_encoder import CrossEncoder
import os
from dotenv import load_dotenv
from utils import get_logger
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
        
        Le modèle est chargé depuis HuggingFace ou configuré via une variable d'environnement.
        Par défaut, utilise le modèle camemBERT optimisé pour le français.
        """
        project_root = os.path.dirname(os.path.abspath(__name__))
        model_path = os.path.join(project_root, "models", "reranking", "mmarco-mMiniLMv2-L12-H384-v1")
        # Nom du modèle, configurable via variable d'environnement
        model_name = os.getenv(
            "CROSS_ENCODER_MODEL",
            "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",  # Modèle par défaut
        )
        try:
            # Tentative de chargement du modèle local
            logger.debug(f"Tentative de chargement local du modèle depuis {model_path}")
            # Initialisation du Cross-Encoder
            self.model = CrossEncoder(model_path)
            logger.debug(f"Modèle chargé localement depuis {model_path}")
        except Exception as e:
            logger.debug(f"Échec du chargement local: {e}. Tentative de chargement en ligne.")
            # Chargement depuis Hugging Face si échec local
            self.model = CrossEncoder(model_name)
            logger.debug(f"Modèle chargé en ligne depuis Hugging Face : {model_name}")

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
        # Création des paires (requête, texte) pour chaque texte
        pairs = [(query, text) for text in texts]
        
        # Prédiction avec le Cross-Encoder
        scores = self.model.predict(pairs, show_progress_bar=False)
        
        return scores
    
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