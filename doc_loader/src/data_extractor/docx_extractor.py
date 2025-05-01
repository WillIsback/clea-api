# docx_extractor.py
from docx import Document
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk
from typing import Iterator
from datetime import date
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from pathlib import Path


class DocxExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        """Initialise un extracteur pour les fichiers DOCX.
        
        Args:
            file_path: Chemin vers le fichier DOCX à traiter.
        """
        super().__init__(file_path)
        self.file_path = Path(file_path)
        self.document = Document(file_path)

    def extract_metadata(self) -> dict:
        """Extrait les métadonnées du fichier DOCX.
        
        Returns:
            Dictionnaire contenant les métadonnées extraites.
        """
        metadata = {}
        try:
            with ZipFile(self.file_path) as docx_zip:
                core_props = docx_zip.read("docProps/core.xml")
                tree = ET.fromstring(core_props)
                for element in tree:
                    tag = element.tag.split("}")[1]
                    metadata[tag] = element.text
        except Exception as e:
            print(f"Erreur lors de l'extraction des métadonnées : {e}")
        return metadata

    def extract_many(self, max_length: int = 1000) -> Iterator[ExtractedDocument]:
        """Extrait le contenu du fichier DOCX en chunks de taille maximale spécifiée.
        
        Itère paragraphe par paragraphe et bufferise en chunks RAM-safe
        via stream_split_to_disk.
        
        Args:
            max_length: Taille maximale d'un chunk. Par défaut 1000.
            
        Returns:
            Un itérateur sur les documents extraits.
        """
        if not self.document.paragraphs:
            return

        meta = {
            "title": self.file_path.name,
            "theme": "Thème générique",
            "document_type": "DOCX",
            "publish_date": date.today(),
            "embedding": None,
        }

        def stream_segments():
            for para in self.document.paragraphs:
                text = para.text.strip()
                if text:
                    yield text + "\n"

        yield from stream_split_to_disk(meta, stream_segments(), max_length=max_length)
