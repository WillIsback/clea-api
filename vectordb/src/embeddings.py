"""
Module de génération d'embeddings vectoriels.

Ce module fournit les outils nécessaires pour transformer des textes
en représentations vectorielles de haute dimension utilisables pour
la recherche sémantique.
"""

from transformers import CamembertModel, CamembertTokenizer
import torch
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class EmbeddingGenerator:
    """Classe responsable de la génération d'embeddings vectoriels et du calcul de similarité cosinus."""

    def __init__(self):
        """Initialise le modèle CamemBERT pour la génération d'embeddings."""
        self.model_name = os.getenv("MODEL_NAME", "camembert-base")
        self.tokenizer = CamembertTokenizer.from_pretrained(self.model_name)
        self.model = CamembertModel.from_pretrained(self.model_name)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()  # Passer explicitement en mode évaluation
        print(f"Modèle d'embedding chargé: {self.model_name} sur {self.device}")

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
