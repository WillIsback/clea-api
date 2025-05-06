"""
Module de génération d'embeddings vectoriels.

Ce module fournit les outils nécessaires pour transformer des textes
en représentations vectorielles de haute dimension utilisables pour
la recherche sémantique.
"""

from transformers import AutoTokenizer, AutoModel
import torch
import os
from typing import List
from dotenv import load_dotenv
from utils import get_logger


load_dotenv()

# Configuration du logger
logger = get_logger("clea-api.vectordb.embeddings")
# ------------------------------------------------------------------ #

class EmbeddingGenerator:
    def __init__(self):
        """Initialise le modèle CamemBERT avec tentative de chargement local en priorité."""
        project_root = os.path.dirname(os.path.abspath(__name__))
        model_path = os.path.join(project_root, "models", "embeddings", "camembertav2-base")
        model_name = os.getenv("EMBEDDING_MODEL", "almanach/camembertav2-base")

        try:
            # Tentative de chargement du modèle local
            logger.debug(f"Tentative de chargement local du modèle depuis {model_path}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            self.model = AutoModel.from_pretrained(model_path, local_files_only=True)
            logger.debug(f"Modèle chargé localement depuis {model_path}")
        except Exception as e:
            logger.debug(f"Échec du chargement local: {e}. Tentative de chargement en ligne.")
            # Chargement depuis Hugging Face si échec local
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            logger.debug(f"Modèle chargé en ligne depuis Hugging Face : {model_name}")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()
        logger.debug(f"Modèle d'embedding prêt sur {self.device}")

    def generate_embedding(self, text: str) -> List[float]:
        """Génère un embedding vectoriel à partir d'un texte.

        Args:
            text: Texte à encoder.

        Returns:
            Liste représentant l'embedding vectoriel.
        """
        # Utiliser la méthode par lots même pour un seul texte
        return self.generate_embeddings_batch([text])[0]

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Génère des embeddings vectoriels pour plusieurs textes en une seule passe.

        Cette méthode optimise le traitement en utilisant le parallélisme du GPU
        pour encoder plusieurs textes simultanément.

        Args:
            texts: Liste des textes à encoder.

        Returns:
            Liste d'embeddings vectoriels, un pour chaque texte d'entrée.

        Raises:
            ValueError: Si la liste de textes est vide.
        """
        if not texts:
            return []

        # Tokenisation de tous les textes avec padding
        inputs = self.tokenizer(
            texts, return_tensors="pt", padding=True, truncation=True, max_length=512
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        # Extraction des embeddings pour chaque texte (token CLS)
        embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()

        # Convertir en liste de listes
        return [embedding.tolist() for embedding in embeddings]


if __name__ == "__main__":
    # Exemple d'utilisation
    generator = EmbeddingGenerator()
    text = "Ceci est un exemple de texte."
    embedding = generator.generate_embedding(text)
    print(f"Embedding pour le texte '{text}': {embedding}")