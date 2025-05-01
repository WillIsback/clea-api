import json
from pathlib import Path
from datetime import date
from typing import Iterator
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk


class JsonExtractor(BaseExtractor):
    """
    Extracteur pour les fichiers JSON.

    :param file_path: Chemin du fichier JSON à extraire
    :type file_path: str
    :raises ValueError: Si le fichier JSON est invalide
    """
    def __init__(self, file_path: str):
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
