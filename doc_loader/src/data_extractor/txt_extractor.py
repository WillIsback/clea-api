from __future__ import annotations

from pathlib import Path
from datetime import date
import json
from ..base import (  # helpers mutualisés
    BaseExtractor,
    build_document_with_chunks,
    DocumentWithChunks,
)


class TxtExtractor(BaseExtractor):
    """
    Convertit un fichier **.txt** en un unique payload
    `DocumentWithChunks`, prêt à être envoyé vers `/database/documents`.
    """

    # ------------------------------------------------------------------ #
    #  Boiler-plate
    # ------------------------------------------------------------------ #
    def __init__(self, file_path: str) -> None:
        super().__init__(file_path)
        self.file_path = Path(file_path)

    # ------------------------------------------------------------------ #
    #  Implémentations BaseExtractor
    # ------------------------------------------------------------------ #

    def extract_one(self, max_length: int = 1_000) -> DocumentWithChunks:
        """
        Extrait un seul objet `DocumentWithChunks` à partir du fichier TXT.

        Args:
            max_length (int): Longueur cible pour les segments finaux.

        Returns:
            DocumentWithChunks: Objet contenant les chunks et métadonnées.

        Raises:
            ValueError: Si le fichier est vide ou si aucune métadonnée valide n'est trouvée.
        """
        if self.file_path.stat().st_size == 0:  # fichier vide ➜ rien à faire
            raise ValueError("Fichier TXT vide")

        # Lecture du contenu du fichier
        full_text = self.file_path.read_text(encoding="utf-8").strip()

        # Vérification si le contenu est une liste JSON
        try:
            entries = json.loads(full_text)
            if isinstance(entries, list) and all(isinstance(e, dict) for e in entries):
                # Extraction des métadonnées depuis la première entrée
                first_entry = entries[0]
                title = first_entry.get("title", self.file_path.stem)
                theme = first_entry.get("theme", "Générique")
                document_type = first_entry.get("document_type", "TXT")
                publish_date = date.fromisoformat(
                    first_entry.get("publish_date", str(date.today()))
                )
                full_text = "\n\n".join(
                    e.get("content", "").strip() for e in entries if e.get("content")
                ).strip()
            else:
                raise ValueError("Le fichier TXT ne contient pas une liste valide.")
        except json.JSONDecodeError:
            # Si le contenu n'est pas une liste JSON, utiliser des valeurs par défaut
            title = self.file_path.stem
            theme = "Générique"
            document_type = "TXT"
            publish_date = date.today()

        # Construction du document avec les chunks
        return build_document_with_chunks(
            title=title,
            theme=theme,
            document_type=document_type,
            publish_date=publish_date,
            max_length=max_length,
            full_text=full_text,
        )
