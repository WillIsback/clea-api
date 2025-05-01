from pathlib import Path
from datetime import date
from typing import Iterator
from bs4 import BeautifulSoup
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk


class HtmlExtractor(BaseExtractor):
    """
    Extracteur pour les fichiers HTML.

    :param file_path: Chemin du fichier HTML à extraire
    :type file_path: str
    :raises ValueError: Si le fichier HTML ne peut pas être lu
    """
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.file_path = Path(file_path)
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.soup = BeautifulSoup(f, "html.parser")
        except Exception as e:
            raise ValueError(f"Erreur lors de la lecture du fichier HTML : {e}")

    def extract_many(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        content = self.soup.get_text(separator="\n").strip()
        if not content:
            return

        meta = {
            "title": self.file_path.name,
            "theme": "Thème générique",
            "document_type": "HTML",
            "publish_date": date.today(),
            "embedding": None,
        }

        def stream_segments():
            for line in content.splitlines():
                yield line + "\n"

        yield from stream_split_to_disk(meta, stream_segments(), max_length=max_length)
