from __future__ import annotations

import json
from datetime import date
from typing import Dict, List

from ..base import BaseExtractor, build_document_with_chunks, DocumentWithChunks


# --------------------------------------------------------------------------- #
#  Extracteur JSON
# --------------------------------------------------------------------------- #
class JsonExtractor(BaseExtractor):
    """
    Extrait des contenus stockés dans un fichier **JSON**.

    Le fichier doit être une liste de dictionnaires :
    ```
    [
        {"title": "...", "content": "...", "theme": "...", ...},
        ...
    ]
    ```
    Chaque entrée génère un **DocumentWithChunks** prêt à être envoyé
    à l’endpoint `POST /database/documents`.
    """

    def __init__(self, file_path: str) -> None:
        """Initialise l'extracteur JSON avec les métadonnées par défaut.

        Args:
            file_path (str): Chemin vers le fichier JSON.

        Raises:
            ValueError: Si le fichier JSON ne peut pas être ouvert ou est vide.
        """
        super().__init__(file_path)
        self.entries: List[Dict[str, str]] = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.entries = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Erreur lors de l'ouverture du fichier JSON : {e}")

    def extract_one(self, *, max_length: int = 1_000) -> DocumentWithChunks:
        if not self.entries:
            raise ValueError("JSON vide")

        # Agrégation des contenus et vérifications
        full_text = "\n\n".join(
            e.get("content", "").strip() for e in self.entries if e.get("content")
        ).strip()
        if not full_text:
            raise ValueError("Aucune entrée 'content' trouvée")

        # Extraction des métadonnées avec valeurs par défaut
        first_entry = self.entries[0]
        title = first_entry.get("title", self.file_path.stem)
        theme = first_entry.get("theme", "Générique")
        document_type = first_entry.get("document_type", "JSON")
        publish_date = date.fromisoformat(
            first_entry.get("publish_date", str(date.today()))
        )

        return build_document_with_chunks(
            title=title,
            theme=theme,
            document_type=document_type,
            publish_date=publish_date,
            max_length=max_length,
            full_text=full_text,
        )
