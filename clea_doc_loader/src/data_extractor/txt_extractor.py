from pathlib import Path
from datetime import date
from typing import Iterator
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk


class TxtExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.file_path = Path(file_path)
        self.meta = {
            "title": self.file_path.name,
            "theme": "Thème générique",
            "document_type": "TXT",
            "publish_date": date.today().isoformat(),
            "embedding": None,
        }

    def extract_many(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        lines = self.file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        yield from stream_split_to_disk(self.meta, iter(lines), max_length)
