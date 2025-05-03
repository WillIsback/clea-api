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
from .constants import MAX_CHUNK_SIZE

# Configuration du logger
logger = logging.getLogger(__name__)

# Patterns pour la détection des sections
_SECTION_PATTERNS = [
    re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE),  # Markdown #
    re.compile(r"^([A-Z].{2,70})\n[=\-]{3,}$", re.MULTILINE),  # Underline
    re.compile(r"^([A-Z][A-Za-z0-9\s\-:,.]{2,70})$", re.MULTILINE),
]


def _extract_semantic_sections(text: str, max_sections: int = 20) -> List[Dict]:
    """
    Extrait les sections sémantiquement significatives du texte.

    Optimisé pour les grands corpus non structurés en détectant les ruptures naturelles
    de contenu et les changements thématiques.

    Args:
        text: Texte à analyser.
        max_sections: Nombre maximum de sections à extraire (augmenté à 20).

    Returns:
        List[Dict]: Liste des sections trouvées (titre, contenu, positions).
    """
    # Recherche des titres de section avec une analyse plus intelligente
    matches = []
    search_limit = min(len(text), 2_000_000)  # Augmenté pour les gros textes

    # 1. Recherche via les patterns standards (titres formels)
    for pattern in _SECTION_PATTERNS:
        for m in pattern.finditer(text[:search_limit]):
            title = m.group(1) if m.lastindex else m.group(0)
            matches.append((title.strip(), m.start(), m.end()))
            if len(matches) >= max_sections * 3:  # Plus de marge pour filtrer
                break

    # 2. Détection intelligente des séparateurs naturels (plusieurs approches)
    if len(matches) < max_sections // 2:
        # 2.1 Recherche de multiples sauts de ligne (séparateurs forts)
        strong_separators = list(re.finditer(r"\n\s*\n\s*\n", text[:search_limit]))

        # 2.2 Détection des ruptures de flux de texte (séparateurs moyens)
        if len(strong_separators) < max_sections // 2:
            medium_separators = list(
                re.finditer(r"\n\s*\n(?=[A-Z])", text[:search_limit])
            )
            strong_separators.extend(medium_separators)

        # 2.3 Division par blocs de taille régulière pour très grands textes non structurés
        artificial_separators = []  # Liste séparée pour les séparateurs artificiels
        if len(strong_separators) < 3 and len(text) > 100_000:
            block_size = min(50_000, len(text) // (max_sections // 2))
            for i in range(1, min(max_sections, len(text) // block_size)):
                # Trouver le prochain saut de ligne après la position cible
                pos = text.find("\n", i * block_size)
                if pos > 0:
                    # Stocker uniquement la position dans une liste séparée
                    artificial_separators.append((pos, pos + 1))  # (start, end)

        # Transformer les séparateurs en sections potentielles
        separators_positions = []

        # Ajouter d'abord les séparateurs trouvés par regex
        for sep in strong_separators:
            separators_positions.append((sep.start(), sep.end()))

        # Ajouter les séparateurs artificiels
        separators_positions.extend(artificial_separators)

        # Trier les positions par ordre croissant
        separators_positions.sort(key=lambda pos: pos[0])

        # Maintenant traiter tous les séparateurs
        if separators_positions:
            prev_end = 0
            for start, end in separators_positions[:max_sections]:
                if start - prev_end > 500:  # Section significative
                    # Recherche d'un titre potentiel
                    context_before = text[max(0, prev_end) : min(prev_end + 200, start)]
                    lines = [
                        line for line in context_before.split("\n") if line.strip()
                    ]

                    # Prendre la première ligne non vide comme titre potentiel
                    potential_title = lines[0].strip() if lines else "Section"
                    if len(potential_title) > 100:
                        potential_title = potential_title[:97] + "..."

                    matches.append((potential_title, prev_end, start))
                prev_end = end

            # Ajouter la dernière section
            if prev_end < len(text) - 1000 and len(matches) < max_sections:
                last_title = "Section finale"
                matches.append((last_title, prev_end, len(text)))

        # Transformer les séparateurs en sections potentielles
        if strong_separators:
            prev_end = 0
            for separator in strong_separators[:max_sections]:
                sep_start = separator.start()
                if sep_start - prev_end > 500:  # Section significative
                    # Recherche d'un titre potentiel
                    context_before = text[
                        max(0, prev_end) : min(prev_end + 200, sep_start)
                    ]
                    lines = [
                        line for line in context_before.split("\n") if line.strip()
                    ]

                    # Prendre la première ligne non vide comme titre potentiel
                    potential_title = lines[0].strip() if lines else "Section"
                    if len(potential_title) > 100:
                        potential_title = potential_title[:97] + "..."

                    matches.append((potential_title, prev_end, sep_start))
                prev_end = separator.end()

            # Ajouter la dernière section
            if prev_end < len(text) - 1000 and len(matches) < max_sections:
                last_title = "Section finale"
                matches.append((last_title, prev_end, len(text)))

    # Trier les sections par position
    matches.sort(key=lambda t: t[1])

    # Si aucune section n'a été trouvée, diviser artificiellement en sections égales
    if not matches and len(text) > 10_000:
        section_size = min(100_000, len(text) // min(max_sections, 10))
        for i in range(min(max_sections, len(text) // section_size)):
            start_pos = i * section_size
            end_pos = min((i + 1) * section_size, len(text))

            # Ajuster aux limites de paragraphes si possible
            if start_pos > 0:
                paragraph_start = text.find("\n\n", start_pos - 200, start_pos + 200)
                if paragraph_start > 0:
                    start_pos = paragraph_start + 2

            title = f"Section {i + 1}"
            # Extraire un bout du début pour générer un titre signifiant
            context = text[start_pos : min(start_pos + 50, end_pos)]
            first_line = context.split("\n", 1)[0].strip()
            if len(first_line) > 5 and len(first_line) < 80:
                title = first_line

            matches.append((title, start_pos, end_pos))

    # Si toujours aucune section, considérer le document entier comme une section
    if not matches:
        first_line = text.strip().split("\n", 1)[0]
        title = first_line[:50] if len(first_line) < 50 else "Document"
        return [
            {"title": title, "content": text, "start_char": 0, "end_char": len(text)}
        ]

    # Générer les sections avec leur contenu
    sections = []
    for i, (title, start, end) in enumerate(matches[:max_sections]):
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
    if sections and matches[0][1] > 0:
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
    text: str, base_offset: int = 0, max_paragraphs: int = 20
) -> List[Dict]:
    """
    Extrait les paragraphes sémantiquement cohérents d'un texte.

    Optimisé pour les grands corpus en utilisant diverses heuristiques de segmentation
    et en augmentant le nombre maximum de paragraphes extraits.

    Args:
        text: Texte à diviser en paragraphes.
        base_offset: Décalage de base pour indexer.
        max_paragraphs: Nombre maximum de paragraphes (augmenté à 20).

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

    # Pour les très grands textes, adapter la stratégie
    if len(text) > 50000:
        ideal_para_length = min(2000, max(500, len(text) // max_paragraphs))
    else:
        ideal_para_length = min(1000, max(300, len(text) // max_paragraphs))

    # 1. Séparation par sauts de ligne multiples (paragraphes explicites)
    raw_blocks = re.split(r"\n\s*\n", text)

    # Si le texte n'a pas de séparation claire de paragraphes
    if len(raw_blocks) < 3 and len(text) > 5000:
        # Approche alternative 1: rechercher des phrases complètes
        sentences = re.split(r"(?<=[.!?])\s+", text)

        # Si trop peu de phrases, découper artificiellement
        if len(sentences) < max_paragraphs:
            # Découpage artificiel du texte en blocs de taille similaire
            desired_count = min(max_paragraphs, max(3, len(text) // ideal_para_length))
            block_size = len(text) // desired_count

            raw_blocks = []
            for i in range(desired_count):
                start_idx = i * block_size
                end_idx = min((i + 1) * block_size, len(text))

                # Chercher la fin d'une phrase si possible
                if i < desired_count - 1:
                    for punct in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
                        end_pos = text.rfind(
                            punct, start_idx + block_size // 2, end_idx
                        )
                        if end_pos > start_idx:
                            end_idx = end_pos + 1
                            break

                block = text[start_idx:end_idx].strip()
                if block:
                    raw_blocks.append(block)
        else:
            # Regrouper les phrases en paragraphes logiques
            raw_blocks = []
            current_block = []
            current_length = 0

            for sentence in sentences:
                if current_length + len(sentence) <= ideal_para_length:
                    current_block.append(sentence)
                    current_length += len(sentence) + 1  # +1 pour l'espace
                else:
                    if current_block:
                        raw_blocks.append(" ".join(current_block))
                    current_block = [sentence]
                    current_length = len(sentence)

            if current_block:
                raw_blocks.append(" ".join(current_block))

    # 2. Regroupement des blocs courts pour former des paragraphes cohérents
    blocks = []
    current_block = []
    current_length = 0

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        if current_length + len(block) <= ideal_para_length * 1.5:
            current_block.append(block)
            current_length += len(block) + 2  # +2 pour '\n\n'
        else:
            if current_block:
                blocks.append("\n\n".join(current_block))
            current_block = [block]
            current_length = len(block)

    if current_block:
        blocks.append("\n\n".join(current_block))

    # 3. Limiter le nombre de paragraphes
    blocks = blocks[:max_paragraphs]

    # 4. Déterminer les positions exactes et créer les paragraphes
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

    # Si aucun paragraphe n'a été trouvé, traiter tout comme un paragraphe
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
    max_chunks: int = 20,
) -> List[Dict]:
    """
    Crée des chunks qui respectent le contenu sémantique du texte.

    Optimisé pour les grands textes avec une meilleure stratégie de découpage
    et un nombre accru de chunks autorisés.

    Args:
        text: Texte à diviser.
        max_length: Longueur maximale d'un chunk.
        min_overlap: Chevauchement minimal entre chunks.
        base_offset: Décalage de base pour l'indexation.
        max_chunks: Nombre maximum de chunks à créer (augmenté à 20).

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

    # Essayer de diviser aux frontières naturelles
    chunks = []
    start = 0
    chunk_count = 0

    # Pour la recherche sémantique, garder des chunks de bonne taille
    effective_max = min(max_length * 1.2, MAX_CHUNK_SIZE)

    # Adapter l'overlap en fonction de la taille du texte
    if len(text) > effective_max * 10:
        # Pour les très grands textes, réduire l'overlap pour avoir plus de couverture
        effective_overlap = min(min_overlap, effective_max // 20)
    else:
        # Sinon garder un overlap significatif pour la continuité sémantique
        effective_overlap = min(min_overlap, effective_max // 10)

    while start < len(text) and chunk_count < max_chunks:
        # Déterminer où terminer ce chunk
        end = min(start + effective_max, len(text))

        # Chercher un point de coupure naturel (phrase complète ou paragraphe)
        if end < len(text):
            # Priorité aux fins de paragraphes
            # Conversion explicite en entiers pour éviter les erreurs de typage
            para_break = text.rfind(
                "\n\n", int(start + (effective_max * 0.5)), int(end)
            )
            if para_break > start + int(effective_max * 0.3):
                end = para_break + 2
            else:
                # Chercher en arrière un point de fin de phrase
                for punct in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
                    sentence_break = text.rfind(
                        punct, int(start + (effective_max * 0.5)), int(end)
                    )
                    if sentence_break > start + int(effective_max * 0.3):
                        end = sentence_break + len(punct)
                        break

        # Extraire le chunk et vérifier sa cohérence
        chunk_text = text[start:end].strip()
        if not chunk_text:
            # Avancer au prochain caractère non-vide
            # Utiliser une expression régulière littérale et convertir en int
            next_non_empty = text.find("\\S", int(start))
            start = next_non_empty if next_non_empty > 0 else end
            continue

        chunks.append(
            {
                "content": chunk_text,
                "start_char": base_offset + start,
                "end_char": base_offset + end,
            }
        )
        chunk_count += 1

        # Adapter l'overlap intelligemment pour éviter les répétitions exactes
        # mais maintenir la continuité sémantique
        if end < len(text):
            # Chercher la fin de phrase précédente pour un overlap propre
            # Conversion explicite en entiers pour éviter les erreurs de typage
            overlap_pos = max(
                text.rfind(". ", int(end - (effective_overlap * 2)), int(end)),
                text.rfind("! ", int(end - (effective_overlap * 2)), int(end)),
                text.rfind("? ", int(end - (effective_overlap * 2)), int(end)),
                text.rfind(".\n", int(end - (effective_overlap * 2)), int(end)),
                text.rfind("!\n", int(end - (effective_overlap * 2)), int(end)),
                text.rfind("?\n", int(end - (effective_overlap * 2)), int(end)),
            )

            if overlap_pos > start and overlap_pos > end - int(effective_overlap * 2):
                next_start = overlap_pos + 2
            else:
                next_start = max(start + 1, end - int(effective_overlap))
        else:
            next_start = end

        start = next_start

    return chunks
