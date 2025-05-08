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
from huggingface_hub import snapshot_download

load_dotenv()

# Configuration du logger
logger = get_logger("clea-api.vectordb.embeddings")
# ------------------------------------------------------------------ #

class EmbeddingGenerator:
    def __init__(self):
        """Initialise le modèle d'embeddings avec gestion automatique des devices."""
        project_root = os.path.dirname(os.path.abspath(__name__))
        model_path = os.path.join(project_root, "models", "embeddings", "camembertav2-base")
        model_name = os.getenv("EMBEDDING_MODEL", "almanach/camembertav2-base")
        self.model_name = model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Indique si nous fonctionnons sur GPU ou CPU
        device_type = "GPU" if torch.cuda.is_available() else "CPU"
        logger.info(f"Initialisation du générateur d'embeddings sur {device_type}")
        
        try:
            # Tentative de chargement local avec device_map="auto"
            logger.debug(f"Tentative de chargement local depuis {model_path} avec device_map=auto")
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            self.model = AutoModel.from_pretrained(
                model_path,
                local_files_only=True,
                device_map="auto",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
            logger.debug(f"Modèle chargé localement avec device_map=auto depuis {model_path}")
        
        except Exception as e:
            # Chargement depuis Hugging Face avec device_map="auto"
            logger.debug(f"Chargement local échoué: {e}. Tentative en ligne avec device_map=auto")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModel.from_pretrained(
                    model_name,
                    device_map="auto",
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
                )
                logger.info(f"Modèle chargé depuis Hugging Face avec device_map=auto: {model_name}")
            
            except Exception as e2:
                # Fallback sur la méthode classique si device_map="auto" échoue
                logger.warning(f"Échec du chargement avec device_map=auto: {e2}. Utilisation de la méthode manuelle.")
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModel.from_pretrained(model_name)
                
                try:
                    self.model.to(self.device)
                except NotImplementedError as e3:
                    if "Cannot copy out of meta tensor" in str(e3):
                        logger.warning("Meta tensor detected, using to_empty() method")
                        self.model = self.model.to_empty(device=self.device)
                        model_path = snapshot_download(model_name)
                        state_dict = torch.load(
                            os.path.join(model_path, "pytorch_model.bin"), 
                            map_location=self.device
                        )
                        self.model.load_state_dict(state_dict, strict=False)
                    else:
                        raise
                
                logger.info(f"Modèle chargé avec méthode manuelle sur {self.device}")

        # Toujours mettre le modèle en mode évaluation
        self.model.eval()
        logger.info(f"Modèle d'embedding prêt - Utilisation: {device_type}")

    # Le reste de votre classe reste inchangé
    def generate_embedding(self, text: str) -> List[float]:
        """Génère un embedding vectoriel à partir d'un texte."""
        return self.generate_embeddings_batch([text])[0]

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Génère des embeddings vectoriels pour plusieurs textes en une seule passe."""
        if not texts:
            return []

        # Tokeniser sur CPU (par défaut)
        inputs = self.tokenizer(
            texts, return_tensors="pt", padding=True, truncation=True, max_length=512
        )
        
        # Déplacer TOUS les tenseurs d'entrée vers le même device que le modèle
        # Avec device_map="auto", nous devons nous assurer que les entrées sont sur le bon device
        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        # Récupérer sur CPU pour la conversion en liste Python
        embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
        return [embedding.tolist() for embedding in embeddings]