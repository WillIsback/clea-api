from pathlib import Path
from datetime import date
from typing import Iterator
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk, adaptive_segmentation, choose_splitter


class TxtExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        """Initialise un extracteur pour les fichiers texte.
        
        Args:
            file_path: Chemin vers le fichier texte à traiter.
        """
        super().__init__(file_path)
        self.file_path = Path(file_path)
        self.meta = {
            "title": self.file_path.name,
            "theme": "Thème générique",
            "document_type": "TXT",
            "publish_date": date.today().isoformat(),
            "embedding": None,
        }

def extract_many(self, max_length: int = 1_000) -> Iterator[ExtractedDocument]:
    """Génère des instances d'ExtractedDocument à partir d'un fichier texte.

    Choisit automatiquement entre deux méthodes d'extraction en fonction de la taille du fichier:
    * **stream_split_to_disk** - faible utilisation de la RAM avec des segments de longueur fixe
    * **adaptive_segmentation** - découpage hiérarchique (Section ▶ Paragraphe ▶ Segment)

    Args:
        max_length: Longueur cible pour les segments finaux (utilisée par les deux méthodes de découpage)

    Yields:
        ExtractedDocument: Segments du document avec métadonnées
    """
    # ------------------------------------------------------------------ #
    # Choix du splitter                                                  #
    # ------------------------------------------------------------------ #
    file_size = self.file_path.stat().st_size
    use_stream = choose_splitter(
        file_size=file_size,
        mime="text/plain",
    ) == "stream"

    if use_stream:
        # --- STREAM --------------------------------------------------- #
        lines = self.file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        yield from stream_split_to_disk(
            self.meta,
            iter(lines),
            chunk_size=max_length * 1_5,
            overlap_size=int(max_length * 0.15),  # 15 %
        )
    else:
        # --- ADAPTIVE ------------------------------------------------- #
        full_text = self.file_path.read_text(encoding="utf-8")
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