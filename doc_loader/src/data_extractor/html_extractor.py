from pathlib import Path
from datetime import date
from typing import Iterator
from bs4 import BeautifulSoup
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk


class HtmlExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        """Initialise un extracteur pour les fichiers HTML.
        
        Args:
            file_path: Chemin vers le fichier HTML à traiter.
            
        Raises:
            ValueError: Si une erreur survient lors de la lecture du fichier HTML.
        """
        super().__init__(file_path)
        self.file_path = Path(file_path)
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.soup = BeautifulSoup(f, "html.parser")
        except Exception as e:
            raise ValueError(f"Erreur lors de la lecture du fichier HTML : {e}")

    def extract_many(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        """Extrait le contenu du fichier HTML en chunks de taille maximale spécifiée.
        
        Args:
            max_length: Taille maximale d'un chunk. Par défaut 1000.
            
        Returns:
            Un itérateur sur les documents extraits.
        """
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
