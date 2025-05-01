from pathlib import Path
from datetime import datetime
from typing import Iterator
from pypdf import PdfReader
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk


class PdfExtractor(BaseExtractor):
    """
    Extracteur pour les fichiers PDF.

    :param file_path: Chemin du fichier PDF à extraire
    :type file_path: str
    """
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.file_path = Path(file_path)
        self.reader = PdfReader(self.file_path)
        info = self.reader.metadata or {}

        creation_date = info.get("/CreationDate")
        if creation_date and creation_date.startswith("D:"):
            try:
                creation_date = (
                    datetime.strptime(creation_date[2:10], "%Y%m%d").date().isoformat()
                )
            except Exception:
                creation_date = datetime.today().isoformat()
        else:
            creation_date = datetime.today().isoformat()

        self.meta = {
            "title": info.get("/Title", self.file_path.name),
            "theme": info.get("/Subject", "Thème générique"),
            "document_type": "PDF",
            "publish_date": creation_date,
            "embedding": None,
        }

    def extract_many(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        page_texts = (page.extract_text() or "" for page in self.reader.pages)
        yield from stream_split_to_disk(self.meta, page_texts, max_length)
