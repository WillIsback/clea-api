from .extractor_factory import get_extractor
from .data_extractor import ExtractedDocument
from typing import Iterator


class DocsLoader:
    def __init__(self, file_path: str):
        self.extractor = get_extractor(file_path)

    def extract_documents(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        return self.extractor.extract_many(max_length=max_length)
