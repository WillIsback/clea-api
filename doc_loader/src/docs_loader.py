from .extractor_factory import get_extractor
from .data_extractor import ExtractedDocument
from typing import Iterator


class DocsLoader:
    """
    Classe pour charger et extraire des documents à partir d'un fichier donné.

    :param file_path: Chemin du fichier à extraire
    :type file_path: str
    """
    def __init__(self, file_path: str):
        """
        Initialise le chargeur de documents avec le chemin du fichier.

        :param file_path: Chemin du fichier à extraire
        :type file_path: str
        """
        self.extractor = get_extractor(file_path)

    def extract_documents(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        """
        Extrait les documents du fichier en utilisant l'extracteur approprié.

        :param max_length: Longueur maximale des documents extraits, defaults to 1000
        :type max_length: int, optional
        :return: Un itérateur sur les documents extraits
        :rtype: Iterator[ExtractedDocument]
        """
        return self.extractor.extract_many(max_length=max_length)
