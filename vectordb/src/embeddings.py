from transformers import CamembertModel, CamembertTokenizer
import torch
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

class EmbeddingGenerator:
    """Classe responsable de la génération d'embeddings vectoriels et du calcul de similarité cosinus.
    """

    def __init__(self):
        """Initialise le modèle CamemBERT pour la génération d'embeddings.
        """
        self.model_name = os.getenv("MODEL_NAME", "camembert-base")
        self.tokenizer = CamembertTokenizer.from_pretrained(self.model_name)
        self.model = CamembertModel.from_pretrained(self.model_name)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        print(f"Modèle d'embedding chargé: {self.model_name} sur {self.device}")
    
    def generate_embedding(self, text):
        """Génère un embedding vectoriel à partir d'un texte.
        
        Args:
            text (str): Texte à encoder.
            
        Returns:
            list: Liste représentant l'embedding vectoriel.
        """
        print(f"Génération d'un embedding pour le texte : {text}")
        inputs = self.tokenizer(text, return_tensors="pt", 
                               padding=True, truncation=True, max_length=512).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Utilisation du CLS token comme embedding du document
        embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy().flatten()
        return embedding.tolist()
    
    def compute_similarity(self, embedding1, embedding2):
        """Calcule la similarité cosinus entre deux embeddings vectoriels.
        
        Args:
            embedding1 (list): Premier vecteur d'embedding.
            embedding2 (list): Second vecteur d'embedding.
            
        Returns:
            float: Score de similarité cosinus entre 0 et 1.
        """
        # Vérification des types
        if not all(isinstance(x, (int, float)) for x in embedding1):
            raise ValueError("embedding1 contient des valeurs non numériques.")
        if not all(isinstance(x, (int, float)) for x in embedding2):
            raise ValueError("embedding2 contient des valeurs non numériques.")
        
        print(f"Calcul de la similarité entre {len(embedding1)} et {len(embedding2)}")
        # Conversion en array numpy
        vec1 = np.array(embedding1, dtype=float)
        vec2 = np.array(embedding2, dtype=float)
        
        # Calcul de la similarité cosinus
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        cos_sim = np.dot(vec1, vec2) / (norm1 * norm2)
        
        # Normaliser à [0, 1] (la similarité cosinus va de -1 à 1)
        return (cos_sim + 1) / 2