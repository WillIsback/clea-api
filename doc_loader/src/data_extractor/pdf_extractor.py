from pathlib import Path
from datetime import datetime, date
from typing import Iterator
from pypdf import PdfReader
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk, adaptive_segmentation, choose_splitter

class PdfExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        """Initialise un extracteur pour les fichiers PDF.
        
        Args:
            file_path: Chemin vers le fichier PDF à traiter.
        """
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

    def extract_many(self, max_length: int = 1_000) -> Iterator[ExtractedDocument]:
        """Génère des instances d'ExtractedDocument à partir d'un fichier PDF.

        Choisit automatiquement entre deux méthodes d'extraction en fonction de la taille du fichier:
        * **stream_split_to_disk** - faible utilisation de la RAM avec des segments de longueur fixe
        * **adaptive_segmentation** - découpage hiérarchique (Section ▶ Paragraphe ▶ Segment)

        Args:
            max_length: Longueur cible pour les segments finaux (utilisée par les deux méthodes de découpage)

        Yields:
            ExtractedDocument: Segments du document avec métadonnées

        Returns:
            None: Si le document ne contient aucune page
        """
        if not self.reader.pages:
            return

        # ------------------------------------------------------------------ #
        # Choix du splitter                                                  #
        # ------------------------------------------------------------------ #
        file_size = self.file_path.stat().st_size
        use_stream = choose_splitter(
            file_size=file_size,
            mime="application/pdf",
        ) == "stream"

        if use_stream:
            # --- STREAM --------------------------------------------------- #
            page_texts = (page.extract_text() or "" for page in self.reader.pages)
            yield from stream_split_to_disk(
                self.meta,
                page_texts,
                chunk_size=max_length * 1_5,
                overlap_size=int(max_length * 0.15),  # 15 %
            )
        else:
            # --- ADAPTIVE ------------------------------------------------- #
            full_text = "\n".join(page.extract_text() or "" for page in self.reader.pages)
            chunks, _stats = adaptive_segmentation(
                full_text,
                max_length=max_length,
                overlap=int(max_length * 0.2),
            )
            for ch in chunks:
                # Assurer les types corrects pour l'instanciation d'ExtractedDocument
                yield ExtractedDocument(
                    title=f"{self.meta['title']} (lvl {ch['hierarchy_level']})",
                    content=ch["content"],
                    theme=str(self.meta["theme"]),
                    document_type=str(self.meta["document_type"]),
                    publish_date=self.meta["publish_date"] if isinstance(self.meta["publish_date"], date) else date.today(),
                    embedding=None,
                )