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
    """
    Exception levée lorsque le type de fichier n'est pas supporté.

    :param message: Message d'erreur décrivant le problème
    :type message: str
    """
    pass


EXTENSION_TO_EXTRACTOR: dict[str, Type[BaseExtractor]] = {
    ".docx": DocxExtractor,
    ".pdf": PdfExtractor,
    ".json": JsonExtractor,
    ".html": HtmlExtractor,
    ".txt": TxtExtractor,
}


def get_extractor(file_path: str) -> BaseExtractor:
    """
    Retourne l'extracteur approprié en fonction de l'extension du fichier.

    :param file_path: Chemin du fichier à extraire
    :type file_path: str
    :raises UnsupportedFileTypeError: Si le type de fichier n'est pas supporté
    :return: Une instance de l'extracteur correspondant au type de fichier
    :rtype: BaseExtractor
    """
    extension = Path(file_path).suffix.lower()
    extractor_cls = EXTENSION_TO_EXTRACTOR.get(extension)

    if not extractor_cls:
        raise UnsupportedFileTypeError(f"Type de fichier non supporté : {extension}")

    return extractor_cls(file_path)
