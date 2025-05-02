"""
Module d'analyse de texte pour l'extraction de structure.

Fournit des fonctions pour:
- Identifier les sections dans un document
- Extraire des paragraphes cohérents
- Créer des chunks sémantiquement significatifs
"""

import re
import logging
from typing import Dict, List

# Constantes locales
from .constants import MAX_CHUNKS, MAX_CHUNK_SIZE

# Configuration du logger
logger = logging.getLogger(__name__)

# Patterns pour la détection des sections
_SECTION_PATTERNS = [
    re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE),  # Markdown #
    re.compile(r"^([A-Z].{2,70})\n[=\-]{3,}$", re.MULTILINE),  # Underline
    re.compile(r"^([A-Z][A-Za-z0-9\s\-:,.]{2,70})$", re.MULTILINE),
]


def _extract_semantic_sections(text: str, max_sections: int = 10) -> List[Dict]:
    """
    Extrait les sections sémantiquement significatives du texte.

    Args:
        text: Texte à analyser.
        max_sections: Nombre maximum de sections à extraire.

    Returns:
        List[Dict]: Liste des sections trouvées (titre, contenu, positions).
    """
    # Recherche des titres de section avec une analyse plus intelligente
    matches = []
    search_limit = min(
        len(text), 500000
    )  # Limitons la recherche pour les très grands textes

    # 1. Recherche via les patterns standards
    for pattern in _SECTION_PATTERNS:
        for m in pattern.finditer(text[:search_limit]):
            title = m.group(1) if m.lastindex else m.group(0)
            matches.append((title.strip(), m.start(), m.end()))
            if len(matches) >= max_sections * 2:  # Surplus pour filtrage ultérieur
                break

    # 2. Détection intelligente des séparateurs naturels (lignes vides multiples)
    if len(matches) < 3 and len(text) > 1000:
        separators = list(re.finditer(r"\n\s*\n\s*\n", text[:search_limit]))
        if separators:
            prev_end = 0
            for separator in separators[:max_sections]:
                if separator.start() - prev_end > 200:  # Section significative
                    # Recherche d'un titre potentiel avant le séparateur
                    potential_title = (
                        text[prev_end : prev_end + 100].strip().split("\n")[0]
                    )
                    if len(potential_title) > 5 and len(potential_title) < 100:
                        matches.append((potential_title, prev_end, separator.start()))
                prev_end = separator.end()

    # Trier les sections par position et limiter le nombre
    matches.sort(key=lambda t: t[1])
    matches = matches[:max_sections]

    # Si aucune section n'a été trouvée, considérer le document entier comme une section
    if not matches:
        # Essayer d'extraire un titre du début du document
        first_line = text.strip().split("\n")[0]
        title = first_line[:50] if len(first_line) < 50 else "Document"
        return [
            {"title": title, "content": text, "start_char": 0, "end_char": len(text)}
        ]

    # Générer les sections avec leur contenu
    sections = []
    for i, (title, start, end) in enumerate(matches):
        next_start = matches[i + 1][1] if i + 1 < len(matches) else len(text)
        section_content = text[end:next_start].strip()

        # Ne pas créer de section vide ou trop petite
        if len(section_content) < 50 and i + 1 < len(matches):
            continue

        sections.append(
            {
                "title": title,
                "content": section_content,
                "start_char": start,
                "end_char": next_start,
            }
        )

    # Ajouter une introduction si nécessaire
    if matches[0][1] > 0:
        intro_content = text[: matches[0][1]].strip()
        if intro_content and len(intro_content) > 50:
            sections.insert(
                0,
                {
                    "title": "Introduction",
                    "content": intro_content,
                    "start_char": 0,
                    "end_char": matches[0][1],
                },
            )

    return sections


def _extract_semantic_paragraphs(
    text: str, base_offset: int = 0, max_paragraphs: int = 10
) -> List[Dict]:
    """
    Extrait les paragraphes sémantiquement cohérents d'un texte.

    Args:
        text: Texte à diviser en paragraphes.
        base_offset: Décalage de base pour indexer.
        max_paragraphs: Nombre maximum de paragraphes à extraire.

    Returns:
        List[Dict]: Liste des paragraphes trouvés avec leurs positions.
    """
    # Si le texte est très court, le traiter comme un seul paragraphe
    if len(text) < 200:
        return [
            {
                "content": text,
                "start_char": base_offset,
                "end_char": base_offset + len(text),
            }
        ]

    paragraphs = []

    # Diviser intelligemment en paragraphes
    blocks = []
    current_block = []
    current_length = 0
    ideal_para_length = min(1000, max(300, len(text) // max_paragraphs))

    # 1. Séparation par lignes vides
    raw_blocks = re.split(r"\n\s*\n", text)

    # 2. Regroupement des blocs courts pour former des paragraphes cohérents
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        if current_length + len(block) <= ideal_para_length * 1.5:
            current_block.append(block)
            current_length += len(block)
        else:
            if current_block:
                blocks.append("\n\n".join(current_block))
            current_block = [block]
            current_length = len(block)

    if current_block:
        blocks.append("\n\n".join(current_block))

    # 3. Limiter le nombre de paragraphes
    blocks = blocks[:max_paragraphs]

    # 4. Déterminer les positions exactes
    pos = 0
    for block in blocks:
        # Chercher la position exacte du bloc dans le texte
        start = text.find(block, pos)
        if start == -1:  # Fallback
            start = pos

        end = start + len(block)
        paragraphs.append(
            {
                "content": block,
                "start_char": base_offset + start,
                "end_char": base_offset + end,
            }
        )

        pos = end

    # Si aucun paragraphe n'a été trouvé, traiter tout le texte comme un paragraphe
    if not paragraphs:
        paragraphs.append(
            {
                "content": text,
                "start_char": base_offset,
                "end_char": base_offset + len(text),
            }
        )

    return paragraphs


def _create_semantic_chunks(
    text: str,
    max_length: int,
    min_overlap: int = 50,
    base_offset: int = 0,
    max_chunks: int = 5,
) -> List[Dict]:
    """
    Crée des chunks qui respectent le contenu sémantique du texte.

    Args:
        text: Texte à diviser.
        max_length: Longueur maximale d'un chunk.
        min_overlap: Chevauchement minimal entre chunks.
        base_offset: Décalage de base pour l'indexation.
        max_chunks: Nombre maximum de chunks à créer.

    Returns:
        List[Dict]: Liste des chunks sémantiquement cohérents.
    """
    if len(text) <= max_length:
        return [
            {
                "content": text,
                "start_char": base_offset,
                "end_char": base_offset + len(text),
            }
        ]

    # Essayer de diviser aux frontières naturelles: phrases ou sauts de ligne
    chunks = []
    start = 0
    chunk_count = 0

    # Pour la recherche sémantique, on préfère des chunks plus grands
    effective_max = min(max_length * 1.5, MAX_CHUNK_SIZE)

    while start < len(text) and chunk_count < max_chunks:
        # Déterminer où terminer ce chunk
        end = min(start + effective_max, len(text))

        # Chercher un point de coupure naturel (phrase complète)
        if end < len(text):
            # Chercher en arrière un point de fin de phrase
            sentence_break = max(
                text.rfind(". ", int(start), int(end)),
                text.rfind("! ", int(start), int(end)),
                text.rfind("? ", int(start), int(end)),
                text.rfind(".\n", int(start), int(end)),
                text.rfind("!\n", int(start), int(end)),
                text.rfind("?\n", int(start), int(end)),
            )

            # Si on trouve une fin de phrase à une position raisonnable
            if sentence_break > start + int(effective_max // 2):
                end = sentence_break + 1
            else:
                # Chercher un saut de ligne
                line_break = text.rfind(
                    "\n", int(start) + int(effective_max // 2), int(end)
                )
                if line_break > 0:
                    end = line_break + 1

        # Extraire le chunk
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                {
                    "content": chunk_text,
                    "start_char": base_offset + start,
                    "end_char": base_offset + end,
                }
            )
            chunk_count += 1

        # Avancer au prochain segment avec chevauchement
        # Chevauchement d'une phrase entière si possible
        overlap = min_overlap
        next_start = end - overlap

        # S'assurer que le chevauchement est sensé
        if next_start <= start:
            next_start = end  # Pas de chevauchement si problème

        start = next_start

    return chunks
