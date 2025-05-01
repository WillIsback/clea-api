# docx_extractor.py
from docx import Document
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk, adaptive_segmentation, choose_splitter
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

    # --------------------------------------------------------------------- #
    # API public                                                             #
    # --------------------------------------------------------------------- #

def extract_many(self, max_length: int = 1_000) -> Iterator[ExtractedDocument]:
    """Génère des instances d'ExtractedDocument à partir d'un fichier DOCX.

    Choisit automatiquement entre deux méthodes d'extraction en fonction de la taille et de la structure du fichier :
    * **stream_split_to_disk** - faible utilisation de la RAM avec des segments de longueur fixe
    * **adaptive_segmentation** - découpage hiérarchique (Section ▶ Paragraphe ▶ Segment)

    Args:
        max_length: Longueur cible pour les segments finaux (utilisée par les deux méthodes de découpage)

    Yields:
        ExtractedDocument: Segments du document avec métadonnées

    Returns:
        None: Si le document ne contient aucun paragraphe
    """
    if not self.document.paragraphs:
        return

    meta = dict(
        title=self.file_path.stem,
        theme="Thème générique",
        document_type="DOCX",
        publish_date=date.today(),
        embedding=None,
    )

    # ------------------------------------------------------------------ #
    # Choix du splitter                                                  #
    # ------------------------------------------------------------------ #
    file_size = self.file_path.stat().st_size
    use_stream = choose_splitter(
        file_size=file_size,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) == "stream"

    if use_stream:
        # --- STREAM --------------------------------------------------- #
        def _segments() -> Iterator[str]:
            for p in self.document.paragraphs:
                txt = p.text.strip()
                if txt:
                    yield txt + "\n"

        yield from stream_split_to_disk(
            meta,
            _segments(),
            chunk_size=max_length * 1_5,   # ex. 1 500
            overlap_size=int(max_length * 0.15),  # 15 %
        )
    else:
        # --- ADAPTIVE ------------------------------------------------- #
        full_text = "\n".join(p.text for p in self.document.paragraphs)
        chunks, _stats = adaptive_segmentation(
            full_text,
            max_length=max_length,
            overlap=int(max_length * 0.2),
        )
        for ch in chunks:
            # Ensure correct types for ExtractedDocument instantiation
            yield ExtractedDocument(
                title=f"{meta['title']} (lvl {ch['hierarchy_level']})",
                content=ch["content"],
                theme=str(meta["theme"]),
                document_type=str(meta["document_type"]),
                publish_date=meta["publish_date"] if isinstance(meta["publish_date"], date) else date.today(),
                embedding=None,
            )
