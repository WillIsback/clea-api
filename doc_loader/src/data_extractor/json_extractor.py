import json
from pathlib import Path
from datetime import date
from typing import Iterator
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk, adaptive_segmentation, choose_splitter

class JsonExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        """Initialise un extracteur pour les fichiers JSON.
        
        Args:
            file_path: Chemin vers le fichier JSON à traiter.
            
        Raises:
            ValueError: Si le fichier JSON est invalide.
        """
        super().__init__(file_path)
        self.file_path = Path(file_path)

        try:
            self.entries = json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Fichier JSON invalide : {e}")

        self.default_meta = {
            "title": self.file_path.name,
            "theme": "Thème générique",
            "document_type": "JSON",
            "publish_date": date.today().isoformat(),
            "embedding": None,
        }

def extract_many(self, max_length: int = 1_000) -> Iterator[ExtractedDocument]:
    """Génère des instances d'ExtractedDocument à partir d'un fichier JSON.

    Traite chaque entrée du fichier JSON et choisit automatiquement entre deux méthodes d'extraction:
    * **stream_split_to_disk** - faible utilisation de la RAM avec des segments de longueur fixe
    * **adaptive_segmentation** - découpage hiérarchique (Section ▶ Paragraphe ▶ Segment)

    Args:
        max_length: Longueur cible pour les segments finaux (utilisée par les deux méthodes de découpage)

    Yields:
        ExtractedDocument: Segments du document avec métadonnées
    """
    if not self.entries:
        return

    for entry in self.entries:
        meta = {
            **self.default_meta,
            "title": entry.get("title", self.default_meta["title"]),
            "theme": entry.get("theme", self.default_meta["theme"]),
            "document_type": entry.get("document_type", self.default_meta["document_type"]),
            "publish_date": entry.get("publish_date", self.default_meta["publish_date"]),
            "embedding": entry.get("embedding"),
        }
        content = entry.get("content", "")
        
        if not content:
            continue
            
        # ------------------------------------------------------------------ #
        # Choix du splitter                                                  #
        # ------------------------------------------------------------------ #
        content_size = len(content)
        use_stream = content_size < 50_000  # Critère simple basé sur la taille du contenu
        
        if use_stream:
            # --- STREAM --------------------------------------------------- #
            yield from stream_split_to_disk(
                meta, 
                iter([content]), 
                chunk_size=max_length * 1_5,
                overlap_size=int(max_length * 0.15),  # 15 %
            )
        else:
            # --- ADAPTIVE ------------------------------------------------- #
            chunks, _stats = adaptive_segmentation(
                content,
                max_length=max_length,
                overlap=int(max_length * 0.2),
            )
            for ch in chunks:
                # Assurer les types corrects pour l'instanciation d'ExtractedDocument
                yield ExtractedDocument(
                    title=f"{meta['title']} (lvl {ch['hierarchy_level']})",
                    content=ch["content"],
                    theme=str(meta["theme"]),
                    document_type=str(meta["document_type"]),
                    publish_date=meta["publish_date"] if isinstance(meta["publish_date"], date) else date.today(),
                    embedding=None,
                )