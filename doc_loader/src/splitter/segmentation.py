"""
Module de segmentation pour les documents textuels.

Contient les algorithmes de segmentation sémantique et de secours:
- Segmentation hiérarchique (niveaux 0 à 3)
- Segmentation de secours (fallback) robuste
"""

import uuid
import logging
from typing import List, Set, Iterator

from vectordb.src.schemas import ChunkCreate
from .text_analysis import (
    _extract_semantic_sections,
    _extract_semantic_paragraphs,
    _create_semantic_chunks,
)
from .text_utils import _get_meaningful_preview

# Constantes locales
from .constants import MAX_CHUNKS, MAX_CHUNK_SIZE, MIN_LEVEL3_LENGTH, MAX_LEVEL3_CHUNKS

# Configuration du logger
logger = logging.getLogger(__name__)


def semantic_segmentation_stream(text: str, max_length: int) -> Iterator[ChunkCreate]:
    """
    Génère les chunks sémantiques d'un document au fil de l'eau.

    Cette fonction implémente une segmentation hiérarchique en mode streaming, avec deux objectifs :
    1. Limiter la consommation mémoire pour les documents volumineux
    2. Optimiser les chunks pour la recherche sémantique

    Args:
        text: Texte à segmenter.
        max_length: Longueur maximale d'un chunk.

    Yields:
        ChunkCreate: Un chunk à la fois, généré dans l'ordre hiérarchique.
    """
    # Compteurs pour surveiller la génération de chunks
    chunk_count = 0
    seen_hashes: Set[int] = set()  # Utilisation de hashes pour éviter la duplication

    # Niveau 0: Document (résumé significatif)
    # On limite le résumé à ~20% du document ou 1000 caractères maximum
    summary_length = min(1000, max(200, len(text) // 5))
    summary = text[:summary_length].strip()

    # Génération de l'ID racine
    doc_id = int(uuid.uuid4())

    # Génération du chunk racine
    root_chunk = ChunkCreate(
        id=doc_id,
        content=summary,
        hierarchy_level=0,
        start_char=0,
        end_char=len(text),
    )

    # Le premier chunk est toujours produit
    yield root_chunk
    chunk_count += 1
    seen_hashes.add(hash(summary))

    # Segmentation intelligente en sections
    sections = _extract_semantic_sections(text, max_sections=min(10, MAX_CHUNKS // 5))

    # Niveau 1: Sections
    for section_idx, section in enumerate(sections):
        if chunk_count >= MAX_CHUNKS - 1:  # Garder une marge
            logger.warning(
                "Limite de chunks atteinte pendant la segmentation des sections"
            )
            break

        section_title = section["title"]
        # Extrait significatif du contenu de la section (pas tout le contenu)
        section_preview = _get_meaningful_preview(section["content"], max_length)
        section_content = f"{section_title}\n\n{section_preview}"

        # Éviter la duplication
        content_hash = hash(section_content)
        if content_hash in seen_hashes:
            continue

        section_id = int(uuid.uuid4())

        section_chunk = ChunkCreate(
            id=section_id,
            content=section_content,
            hierarchy_level=1,
            start_char=section["start_char"],
            end_char=section["end_char"],
            parent_chunk_id=doc_id,
        )

        # Génération du chunk de section
        yield section_chunk
        chunk_count += 1
        seen_hashes.add(content_hash)

        # Niveau 2: Paragraphes sémantiquement significatifs
        paragraphs = _extract_semantic_paragraphs(
            section["content"],
            base_offset=section["start_char"],
            max_paragraphs=min(5, (MAX_CHUNKS - chunk_count) // 3),
        )

        for para_idx, paragraph in enumerate(paragraphs):
            if chunk_count >= MAX_CHUNKS - 2:  # Garder une marge
                logger.warning(
                    "Limite de chunks atteinte pendant la segmentation des paragraphes"
                )
                break

            para_content = paragraph["content"].strip()
            if (
                not para_content or len(para_content) < 50
            ):  # Ignorer les paragraphes trop courts
                continue

            # Éviter la duplication
            para_hash = hash(para_content)
            if para_hash in seen_hashes:
                continue

            para_id = int(uuid.uuid4())

            # Créer un chunk de paragraphe sans copier le titre de la section
            para_chunk = ChunkCreate(
                id=para_id,
                content=para_content,
                hierarchy_level=2,
                start_char=paragraph["start_char"],
                end_char=paragraph["end_char"],
                parent_chunk_id=section_id,
            )

            # Génération du chunk de paragraphe
            yield para_chunk
            chunk_count += 1
            seen_hashes.add(para_hash)

            # Niveau 3: Uniquement pour les paragraphes vraiment longs
            if len(para_content) > max(max_length * 2, MIN_LEVEL3_LENGTH * 3):
                semantic_chunks = _create_semantic_chunks(
                    para_content,
                    max_length,
                    min_overlap=max_length // 10,  # Overlap limité mais significatif
                    base_offset=paragraph["start_char"],
                    max_chunks=min(MAX_LEVEL3_CHUNKS, MAX_CHUNKS - chunk_count),
                )

                for chunk_idx, sem_chunk in enumerate(semantic_chunks):
                    if chunk_count >= MAX_CHUNKS:
                        break

                    chunk_content = sem_chunk["content"].strip()
                    if (
                        len(chunk_content) < MIN_LEVEL3_LENGTH
                    ):  # Ignorer les chunks trop petits
                        continue

                    # Éviter la duplication
                    chunk_hash = hash(chunk_content)
                    if chunk_hash in seen_hashes:
                        continue

                    sub_chunk = ChunkCreate(
                        id=int(uuid.uuid4()),
                        content=chunk_content,
                        hierarchy_level=3,
                        start_char=sem_chunk["start_char"],
                        end_char=sem_chunk["end_char"],
                        parent_chunk_id=para_id,
                    )

                    # Génération du chunk de niveau 3
                    yield sub_chunk
                    chunk_count += 1
                    seen_hashes.add(chunk_hash)

    logger.info(f"Segmentation sémantique terminée: {chunk_count} chunks générés")


def _semantic_segmentation(text: str, max_length: int) -> List[ChunkCreate]:
    """
    Segmente le texte en respectant son contenu sémantique pour optimiser la recherche vectorielle.

    Utilise l'approche streaming en interne mais retourne une liste complète pour
    compatibilité avec le code existant.

    Args:
        text: Texte à segmenter.
        max_length: Longueur maximale d'un chunk.

    Returns:
        List[ChunkCreate]: Liste des chunks créés avec leur hiérarchie complète.
    """
    from itertools import islice

    # Utiliser le générateur avec une limite sur le nombre de chunks
    chunks = list(islice(semantic_segmentation_stream(text, max_length), MAX_CHUNKS))
    return chunks


def fallback_segmentation_stream(text: str, max_length: int) -> Iterator[ChunkCreate]:
    """
    Version streaming de la segmentation de secours pour économiser de la mémoire.

    Args:
        text: Texte à segmenter.
        max_length: Longueur maximale d'un chunk.

    Yields:
        ChunkCreate: Les chunks générés un par un.
    """
    doc_id = int(uuid.uuid4())
    chunk_count = 0

    # Chunk racine avec aperçu du document
    root_chunk = ChunkCreate(
        id=doc_id,
        content=text[: min(1000, len(text))],
        hierarchy_level=0,
        start_char=0,
        end_char=len(text),
    )
    yield root_chunk
    chunk_count += 1

    # Si le texte est court, on s'arrête là
    if len(text) <= max_length * 1.5:
        return

    # Sinon, on divise en segments de taille appropriée pour la recherche
    effective_length = min(
        max_length * 2, MAX_CHUNK_SIZE
    )  # Chunks plus grands pour recherche sémantique
    start = 0

    while start < len(text) and chunk_count < MAX_CHUNKS:
        # Calculer la fin du segment
        end = min(start + effective_length, len(text))

        # Éviter de couper au milieu d'une phrase
        if end < len(text):
            # Chercher un point de coupure naturel
            for sep in [". ", ".\n", "! ", "!\n", "? ", "?\n", "\n\n"]:
                pos = text.rfind(sep, start + effective_length // 2, end)
                if pos > 0:
                    end = pos + 1 if sep.endswith(" ") else pos + 2
                    break

            # Si aucun séparateur n'a été trouvé, éviter de couper un mot
            if end == start + effective_length and text[end - 1].isalnum():
                pos = text.rfind(" ", start + effective_length // 2, end)
                if pos > 0:
                    end = pos + 1

        chunk_content = text[start:end].strip()
        if chunk_content:
            chunk_id = int(uuid.uuid4())
            yield ChunkCreate(
                id=chunk_id,
                content=chunk_content,
                hierarchy_level=1,
                start_char=start,
                end_char=end,
                parent_chunk_id=doc_id,
            )
            chunk_count += 1

        # Avancer au prochain segment (avec un petit chevauchement pour la continuité)
        overlap = min(100, effective_length // 10)
        start = end - overlap

    logger.info(f"Segmentation de secours terminée: {chunk_count} chunks générés")


def _fallback_segmentation(text: str, max_length: int) -> List[ChunkCreate]:
    """
    Segmentation de secours simplifiée mais robuste en cas d'échec de la segmentation principale.

    Utilise l'approche streaming en interne mais retourne une liste complète pour
    compatibilité avec le code existant.

    Args:
        text: Texte à segmenter.
        max_length: Longueur maximale d'un chunk.

    Returns:
        List[ChunkCreate]: Liste des chunks créés.
    """
    from itertools import islice

    # Utiliser le générateur avec une limite sur le nombre de chunks
    chunks = list(islice(fallback_segmentation_stream(text, max_length), MAX_CHUNKS))
    return chunks
