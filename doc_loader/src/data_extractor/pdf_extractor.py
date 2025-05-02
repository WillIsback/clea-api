from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from pypdf import PdfReader

from ..base import (  # helpers mutualisés
    BaseExtractor,
    build_document_with_chunks,
    DocumentWithChunks,
)


_DATE_RX = re.compile(r"D:(\d{4})(\d{2})(\d{2})")  # -> YYYY MM DD


class PdfExtractor(BaseExtractor):
    """
    Convertit un fichier **.pdf** en un unique payload
    `DocumentWithChunks`, prêt à être inséré via `/database/documents`.
    """

    # ------------------------------------------------------------------ #
    #  Boiler-plate
    # ------------------------------------------------------------------ #
    def __init__(self, file_path: str) -> None:
        super().__init__(file_path)
        self.file_path = Path(file_path)

        self.reader = PdfReader(self.file_path)
        self._publish_date = self._parse_creation_date()

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    def _parse_creation_date(self) -> date:
        """Extrait la date de création si disponible, sinon *today()*."""
        raw = (self.reader.metadata or {}).get("/CreationDate", "")
        m = _DATE_RX.match(raw)
        try:
            return (
                datetime.strptime("".join(m.groups()), "%Y%m%d").date()
                if m
                else date.today()
            )
        except Exception:
            return date.today()

    # ------------------------------------------------------------------ #

    def extract_one(self, max_length: int = 1_000) -> DocumentWithChunks:
        """
        Extrait un seul objet `DocumentWithChunks` à partir du fichier PDF.

        Args:
            max_length (int): Longueur cible pour les segments finaux.

        Returns:
            DocumentWithChunks: Objet contenant les chunks et métadonnées.
        """
        if not self.reader.pages:  # PDF vide ➜ rien à faire
            raise ValueError(
                f"Le fichier {self.file_path} ne contient pas de pages PDF."
            )

        full_text = "\n".join(
            page.extract_text() or "" for page in self.reader.pages
        ).strip()

        return build_document_with_chunks(
            title=(self.reader.metadata or {}).get("/Title", self.file_path.stem),
            theme=(self.reader.metadata or {}).get("/Subject", "Générique"),
            document_type="PDF",
            publish_date=self._publish_date,
            max_length=max_length,
            full_text=full_text,
        )
