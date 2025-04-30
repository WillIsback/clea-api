from pathlib import Path
from .data_extractor import (
    BaseExtractor,
    DocxExtractor,
    PdfExtractor,
    JsonExtractor,
    HtmlExtractor,
    TxtExtractor,
)
from typing import Type


class UnsupportedFileTypeError(Exception):
    pass


EXTENSION_TO_EXTRACTOR: dict[str, Type[BaseExtractor]] = {
    ".docx": DocxExtractor,
    ".pdf": PdfExtractor,
    ".json": JsonExtractor,
    ".html": HtmlExtractor,
    ".txt": TxtExtractor,
}


def get_extractor(file_path: str) -> BaseExtractor:
    extension = Path(file_path).suffix.lower()
    extractor_cls = EXTENSION_TO_EXTRACTOR.get(extension)

    if not extractor_cls:
        raise UnsupportedFileTypeError(f"Type de fichier non supporté : {extension}")

    return extractor_cls(file_path)
