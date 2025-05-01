from pathlib import Path
from datetime import date
from typing import Iterator
from bs4 import BeautifulSoup
from .base import BaseExtractor, ExtractedDocument, stream_split_to_disk, adaptive_segmentation, choose_splitter


class HtmlExtractor(BaseExtractor):
    def __init__(self, file_path: str):
        """Initialise un extracteur pour les fichiers HTML.
        
        Args:
            file_path: Chemin vers le fichier HTML à traiter.
            
        Raises:
            ValueError: Si une erreur survient lors de la lecture du fichier HTML.
        """
        super().__init__(file_path)
        self.file_path = Path(file_path)
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.soup = BeautifulSoup(f, "html.parser")
        except Exception as e:
            raise ValueError(f"Erreur lors de la lecture du fichier HTML : {e}")

    def extract_many(self, max_length: int = 1_000) -> Iterator[ExtractedDocument]:
        """Génère des instances d'ExtractedDocument à partir d'un fichier HTML.

        Choisit automatiquement entre deux méthodes d'extraction en fonction de la taille et de la structure du fichier:
        * **stream_split_to_disk** - faible utilisation de la RAM avec des segments de longueur fixe
        * **adaptive_segmentation** - découpage hiérarchique (Section ▶ Paragraphe ▶ Segment)

        Args:
            max_length: Longueur cible pour les segments finaux (utilisée par les deux méthodes de découpage)

        Yields:
            ExtractedDocument: Segments du document avec métadonnées

        Returns:
            None: Si le document ne contient aucun contenu textuel
        """
        content = self.soup.get_text(separator="\n").strip()
        if not content:
            return

        meta = {
            "title": self.file_path.name,
            "theme": "Thème générique",
            "document_type": "HTML",
            "publish_date": date.today(),
            "embedding": None,
        }

        # ------------------------------------------------------------------ #
        # Choix du splitter                                                  #
        # ------------------------------------------------------------------ #
        file_size = self.file_path.stat().st_size
        use_stream = choose_splitter(
            file_size=file_size,
            mime="text/html",
        ) == "stream"

        if use_stream:
            # --- STREAM --------------------------------------------------- #
            def stream_segments():
                for line in content.splitlines():
                    yield line + "\n"

            yield from stream_split_to_disk(
                meta, 
                stream_segments(), 
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
                    publish_date=meta["publish_date"],  # Déjà un objet date
                    embedding=None,
                )