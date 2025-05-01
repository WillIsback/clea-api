import json
from pathlib import Path
from datetime import date
from typing import Iterator
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk


class JsonExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        """Initialise un extracteur pour les fichiers JSON.
        
        Args:
            file_path: Chemin vers le fichier JSON à traiter.
            
        Raises:
            ValueError: Si le fichier JSON est invalide.
        """
        super().__init__(file_path)
        self.file_path = Path(file_path)

        try:
            self.entries = json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Fichier JSON invalide : {e}")

        self.default_meta = {
            "title": self.file_path.name,
            "theme": "Thème générique",
            "document_type": "JSON",
            "publish_date": date.today().isoformat(),
            "embedding": None,
        }

    def extract_many(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        """Extrait le contenu du fichier JSON en chunks de taille maximale spécifiée.
        
        Args:
            max_length: Taille maximale d'un chunk. Par défaut 1000.
            
        Returns:
            Un itérateur sur les documents extraits.
        """
        for entry in self.entries:
            meta = {
                **self.default_meta,
                "title": entry.get("title", self.default_meta["title"]),
                "theme": entry.get("theme", self.default_meta["theme"]),
                "document_type": entry.get(
                    "document_type", self.default_meta["document_type"]
                ),
                "publish_date": entry.get(
                    "publish_date", self.default_meta["publish_date"]
                ),
                "embedding": entry.get("embedding"),
            }
            content = entry.get("content", "")
            yield from stream_split_to_disk(meta, iter([content]), max_length)
