# vectordb/src/ranking.py
from typing import Sequence, List
from sentence_transformers.cross_encoder import CrossEncoder
import os
from dotenv import load_dotenv

load_dotenv()


class ResultRanker:
    """Renvoie le score de similarité Cross-Encoder pour chaque texte."""

    def __init__(self) -> None:
        model_name = os.getenv(
            "CROSS_ENCODER_MODEL",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        self.model = CrossEncoder(model_name)
        print(f"Modèle de ranking chargé : {model_name}")

    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_text(obj) -> str | None:
        """Petit helper pour extraire le texte d'un objet.

        Args:
            obj: L'objet à analyser, qui peut être une chaîne, un dictionnaire ou un objet avec un attribut `content`.

        Returns:
            str | None: Le texte extrait ou None si aucun texte valide n'est trouvé.
        """
        if isinstance(obj, str):
            return obj.strip() or None
        if isinstance(obj, dict):
            txt = obj.get("content")
            if isinstance(txt, str):
                return txt.strip() or None
        if hasattr(obj, "content"):
            content = getattr(obj, "content", None)
            if isinstance(content, str):
                return content.strip() or None
        return None

    # ------------------------------------------------------------------ #

    def rank_results(self, query: str, texts: Sequence[str]) -> List[float]:
        """Retourne **les scores**, pas les documents triés."""

        # extraction + filtrage éventuel
        pairs: list[tuple[str, str]] = []
        for txt in texts:
            cleaned = self._extract_text(txt)
            if cleaned:
                pairs.append((query, cleaned))
            else:
                pairs.append((query, ""))  # keep alignment, score sera faible

        # prédiction Cross-Encoder
        scores = self.model.predict(pairs, convert_to_numpy=True).tolist()
        return scores  # <-- liste de float
