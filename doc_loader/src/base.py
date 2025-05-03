"""
doc_loader.base (v2)
--------------------

Outils communs pour tous les extracteurs (PDF, DOCX, HTML…).

• ExtractedDocument  – schéma de sortie « brut »
• BaseExtractor      – interface abstraite
• build_document_with_chunks() – normalise stream/adaptive  →  DocumentWithChunks
"""

from __future__ import annotations

import re
import tempfile
import logging
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path


# ------ dépendances internes (évite l'import circulaire au runtime) ----------
from vectordb.src.schemas import DocumentCreate, ChunkCreate, DocumentWithChunks

# ------ modules internes de data_extractor ------------------------------
from doc_loader.src.splitter import (
    _semantic_segmentation,
    _fallback_segmentation,
    MAX_CHUNK_SIZE,
    MAX_TEXT_LENGTH,
    THRESHOLD_LARGE,
    MAX_CHUNKS,
)

# --------------------------------------------------------------------------- #
#  Configuration du logger
# --------------------------------------------------------------------------- #
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Constantes
# --------------------------------------------------------------------------- #
_TMP = Path(tempfile.gettempdir())
_TMP.mkdir(parents=True, exist_ok=True)


# Configuration pour les patterns de section (déplacé vers text_analysis.py)
_SECTION_PATTERNS = [
    re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE),  # Markdown #
    re.compile(r"^([A-Z].{2,70})\n[=\-]{3,}$", re.MULTILINE),  # Underline
    re.compile(r"^([A-Z][A-Za-z0-9\s\-:,.]{2,70})$", re.MULTILINE),
]


# --------------------------------------------------------------------------- #
#  Interface de base des extracteurs
# --------------------------------------------------------------------------- #
class BaseExtractor(ABC):
    """
    Interface abstraite pour tous les extracteurs de documents.

    Attributes:
        file_path (Path): Chemin vers le fichier à extraire.
    """

    def __init__(self, file_path: str) -> None:
        """
        Initialise un extracteur avec le chemin du fichier.

        Args:
            file_path: Chemin vers le fichier à extraire.
        """
        self.file_path = Path(file_path)

    @abstractmethod
    def extract_one(self, *, max_length: int = 1_000) -> DocumentWithChunks:
        """
        Retourne un seul DocumentWithChunks prêt pour la DB.

        Args:
            max_length: Longueur maximale d'un chunk. Défaut à 1000.

        Returns:
            DocumentWithChunks: Document avec ses chunks hiérarchiques.

        Raises:
            NotImplementedError: Si la méthode n'est pas implémentée dans la classe dérivée.
        """
        pass


# --------------------------------------------------------------------------- #
#  Fabrique « DocumentWithChunks » (stream ou adaptive)
# --------------------------------------------------------------------------- #
def build_document_with_chunks(
    title: str,
    theme: str,
    document_type: str,
    publish_date: date,
    max_length: int,
    full_text: str,
) -> DocumentWithChunks:
    """Crée un DocumentWithChunks à partir d'un texte complet.

    Cette fonction analyse le texte fourni et le découpe en fragments hiérarchiques
    (chunks) en utilisant soit une segmentation sémantique, soit une segmentation de
    secours en cas d'échec.

    Args:
        title: Titre du document.
        theme: Thème ou catégorie du document.
        document_type: Type du document (PDF, DOCX, HTML, etc.).
        publish_date: Date de publication du document.
        max_length: Longueur maximale souhaitée pour chaque chunk.
        full_text: Contenu textuel complet du document.

    Returns:
        DocumentWithChunks: Structure contenant les métadonnées du document et
            l'ensemble des chunks générés hiérarchiquement.

    Raises:
        ValueError: Si le texte dépasse la taille maximale autorisée ou si les
            paramètres sont invalides.
    """
    # Validation des entrées
    if not full_text:
        logger.warning("Texte vide reçu dans build_document_with_chunks")
        full_text = "Document vide"

    if len(full_text) > MAX_TEXT_LENGTH:
        logger.warning(f"Texte trop volumineux ({len(full_text)} caractères) - tronqué")
        # Assurons-nous que l'index est un entier
        full_text = full_text[: int(MAX_TEXT_LENGTH)]

    # Validation max_length
    if max_length <= 0:
        logger.warning(
            f"max_length invalide ({max_length}), valeur par défaut utilisée"
        )
        max_length = 1000
    elif max_length > MAX_CHUNK_SIZE:
        logger.warning(
            f"max_length trop grande ({max_length}), limitée à {MAX_CHUNK_SIZE}"
        )
        max_length = int(MAX_CHUNK_SIZE)  # Conversion explicite en entier

    doc_meta = DocumentCreate(
        title=title,
        theme=theme,
        document_type=document_type,
        publish_date=publish_date or date.today(),
    )

    # ------------------------------------------------------------------ #
    # 1) mini-documents : un seul chunk suffit
    # ------------------------------------------------------------------ #
    if len(full_text) <= max_length:
        root = ChunkCreate(
            content=full_text,
            start_char=0,
            end_char=len(full_text),
            hierarchy_level=0,
        )
        return DocumentWithChunks(document=doc_meta, chunks=[root])

    # ------------------------------------------------------------------ #
    # 2) texte plus long : segmentation hiérarchique sémantique
    # ------------------------------------------------------------------ #
    try:
        # Assurons-nous que max_length est un entier pour la segmentation
        chunks = _semantic_segmentation(full_text, int(max_length))
        return DocumentWithChunks(document=doc_meta, chunks=chunks)

    except Exception as e:
        logger.error(f"Erreur pendant la segmentation: {str(e)}", exc_info=True)
        # Segmentation de secours (fallback)
        try:
            chunks = _fallback_segmentation(full_text, int(max_length))
            return DocumentWithChunks(document=doc_meta, chunks=chunks)
        except Exception as fallback_error:
            logger.error(
                f"Échec de la segmentation de secours: {str(fallback_error)}",
                exc_info=True,
            )
            # Dernier recours: un seul chunk avec le début du texte
            root = ChunkCreate(
                content=full_text[: int(max_length)],
                start_char=0,
                end_char=min(len(full_text), int(max_length)),
                hierarchy_level=0,
            )
            return DocumentWithChunks(document=doc_meta, chunks=[root])
