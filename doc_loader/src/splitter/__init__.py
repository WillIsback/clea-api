"""
Package splitter pour la segmentation sémantique des documents.

Fournit les outils pour segmenter des documents textuels en chunks
hiérarchiques optimisés pour la recherche vectorielle.
"""

from .constants import (
    THRESHOLD_LARGE,
    MAX_CHUNKS,
    MAX_TEXT_LENGTH,
    MAX_CHUNK_SIZE,
    MIN_LEVEL3_LENGTH,
    MAX_LEVEL3_CHUNKS,
)

from .segmentation import (
    _semantic_segmentation,
    _fallback_segmentation,
    semantic_segmentation_stream,
    fallback_segmentation_stream,
)

__all__ = [
    # Fonctions de segmentation
    "_semantic_segmentation",
    "_fallback_segmentation",
    "semantic_segmentation_stream",
    "fallback_segmentation_stream",
    # Constantes
    "THRESHOLD_LARGE",
    "MAX_CHUNKS",
    "MAX_TEXT_LENGTH",
    "MAX_CHUNK_SIZE",
    "MIN_LEVEL3_LENGTH",
    "MAX_LEVEL3_CHUNKS",
]
