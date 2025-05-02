from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup, Tag

from ..base import (  # helpers communs
    BaseExtractor,
    build_document_with_chunks,
    DocumentWithChunks,
)


# --------------------------------------------------------------------------- #
#  Extracteur HTML
# --------------------------------------------------------------------------- #
class HtmlExtractor(BaseExtractor):
    """
    Convertit n’importe quel document **HTML** en un ou plusieurs
    payloads `DocumentWithChunks` prêts pour l’endpoint
    `POST /database/documents`.

    Le titre du `<title>` ou du nom de fichier est utilisé comme
    `document.title`.
    Tout le texte visible (sans balises) est extrait.
    """

    def __init__(self, file_path: str) -> None:
        """
        Initialise l'extracteur HTML avec les métadonnées par défaut.

        Args:
            file_path (str): Chemin vers le fichier HTML.

        Raises:
            ValueError: Si le fichier HTML ne peut pas être lu.
        """
        super().__init__(file_path)
        try:
            self._html = Path(file_path).read_text(encoding="utf-8")
            self._soup = BeautifulSoup(self._html, "html.parser")
        except Exception as err:
            raise ValueError(f"Impossible de lire le fichier HTML : {err}") from err

        # Extraction des métadonnées ou utilisation des valeurs par défaut
        self.default_meta = self._extract_metadata()

    def iter_text(self) -> Iterator[str]:
        """
        Renvoie le texte brut, ligne par ligne (utile pour le *stream*).

        Returns:
            Iterator[str]: Texte brut extrait du document HTML.
        """
        for line in self._soup.get_text(separator="\n").splitlines():
            line = line.strip()
            if line:
                yield line + "\n"

    def extract_one(self, max_length: int = 1_000) -> DocumentWithChunks:
        """
        Extrait un seul objet `DocumentWithChunks` à partir du fichier HTML.

        Args:
            max_length (int): Longueur cible pour les segments finaux.

        Returns:
            DocumentWithChunks: Objet contenant les chunks et métadonnées.

        Raises:
            ValueError: Si aucun contenu n'est extrait du document HTML.
        """
        full_text = "\n".join(self.iter_text()).strip()
        if not full_text:
            raise ValueError("Aucun contenu extrait du document HTML.")

        return build_document_with_chunks(
            title=self.default_meta["title"],
            theme=self.default_meta["theme"],
            document_type=self.default_meta["document_type"],
            publish_date=self.default_meta["publish_date"],
            max_length=max_length,
            full_text=full_text,
        )

    def _extract_metadata(self) -> dict:
        """
        Extrait les métadonnées à partir des balises HTML standard.

        Returns:
            dict: Métadonnées extraites ou valeurs par défaut.
        """
        title = self._guess_title()
        theme = self._extract_meta_tag("theme") or "Générique"
        document_type = self._extract_meta_tag("document_type") or "HTML"
        publish_date = self._extract_meta_tag("publish_date")
        try:
            publish_date = (
                date.fromisoformat(publish_date) if publish_date else date.today()
            )
        except ValueError:
            publish_date = date.today()

        return {
            "title": title,
            "theme": theme,
            "document_type": document_type,
            "publish_date": publish_date,
        }

    def _guess_title(self) -> str:
        """
        Devine le titre du document à partir de la balise <title>.

        Returns:
            str: Titre extrait ou nom du fichier.
        """
        if title_tag := self._soup.title:
            return title_tag.get_text(strip=True) or self.file_path.stem
        return self.file_path.stem

    def _extract_meta_tag(self, name: str) -> str | None:
        """
        Extrait le contenu d'une balise <meta> spécifique.

        Args:
            name (str): Nom de l'attribut `name` ou `property` de la balise <meta>.

        Returns:
            str | None: Contenu de la balise <meta> ou None si non trouvé.
        """
        meta_tag = self._soup.find("meta", attrs={"name": name}) or self._soup.find(
            "meta", attrs={"property": name}
        )
        if isinstance(meta_tag, Tag) and "content" in meta_tag.attrs:
            return str(meta_tag["content"]).strip()
        return None
