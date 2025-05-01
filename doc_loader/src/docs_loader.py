from .extractor_factory import get_extractor
from .data_extractor import ExtractedDocument
from typing import Iterator


class DocsLoader:
    def __init__(self, file_path: str):
        """Initialise un chargeur de documents basé sur le type de fichier.
        
        Args:
            file_path: Chemin vers le fichier à traiter.
        """
        self.extractor = get_extractor(file_path)

    def extract_documents(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        """Extrait les documents du fichier en chunks de taille maximale spécifiée.
        
        Args:
            max_length: Taille maximale d'un chunk. Par défaut 1000.
            
        Returns:
            Un itérateur sur les documents extraits.
        """
        return self.extractor.extract_many(max_length=max_length)
