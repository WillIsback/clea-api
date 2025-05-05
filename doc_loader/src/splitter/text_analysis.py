"""
Module d'analyse de texte pour l'extraction de structure.

Fournit des fonctions pour:
- Identifier les sections dans un document
- Extraire des paragraphes cohérents
- Créer des chunks sémantiquement significatifs
"""

import re
from typing import Dict, List
from utils import get_logger

# Constantes locales
from .constants import MAX_CHUNK_SIZE


# Configuration du logger
logger = get_logger("doc_loader.splitter.text_analysis")
# --------------------------------------------------------------------------- #

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
    """Crée des chunks sémantiquement cohérents à partir d'un texte.

    Cette fonction découpe le texte en respectant au mieux les frontières naturelles
    (fins de paragraphes, phrases) pour préserver le contexte sémantique. Elle est
    optimisée pour gérer les grands textes et inclut un chevauchement contrôlé pour
    maintenir la continuité entre les chunks.

    Args:
        text: Texte à diviser en chunks.
        max_length: Longueur maximale souhaitée pour chaque chunk.
        min_overlap: Chevauchement minimal entre chunks consécutifs.
        base_offset: Décalage à appliquer aux positions dans le document original.
        max_chunks: Nombre maximal de chunks à créer.

    Returns:
        Liste de dictionnaires contenant le contenu et les positions des chunks.
        Format: [{"content": str, "start_char": int, "end_char": int}, ...]
    """
    # Convertir tous les paramètres en entiers pour éviter les erreurs de type
    max_length = int(max_length)
    min_overlap = int(min_overlap)
    base_offset = int(base_offset)
    max_chunks = int(max_chunks)

    logger.debug(
        f"Entrée _create_semantic_chunks: max_length={max_length}, min_overlap={min_overlap}, max_chunks={max_chunks}"
    )

    if len(text) <= max_length:
        logger.debug(
            f"Texte court ({len(text)} <= {max_length}): retourne chunk unique"
        )
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
    # Calcul intermédiaire pour éviter les erreurs de type
    temp_max = (max_length * 12) // 10  # équivalent à max_length * 1.2
    effective_max = min(temp_max, MAX_CHUNK_SIZE)
    logger.debug(
        f"effective_max calculé: {effective_max} (type: {type(effective_max).__name__})"
    )

    # Adapter l'overlap en fonction de la taille du texte
    if len(text) > effective_max * 10:
        # Pour les très grands textes, réduire l'overlap pour avoir plus de couverture
        effective_overlap = min(min_overlap, effective_max // 20)
    else:
        # Sinon garder un overlap significatif pour la continuité sémantique
        effective_overlap = min(min_overlap, effective_max // 10)

    logger.debug(
        f"effective_overlap calculé: {effective_overlap} (type: {type(effective_overlap).__name__})"
    )

    while start < len(text) and chunk_count < max_chunks:
        logger.debug(
            f"Itération {chunk_count + 1}: start={start}, type(start)={type(start).__name__}"
        )

        # Déterminer où terminer ce chunk
        end = min(start + effective_max, len(text))
        logger.debug(f"end initial: {end} (type: {type(end).__name__})")

        # Chercher un point de coupure naturel (phrase complète ou paragraphe)
        if end < len(text):
            # Priorité aux fins de paragraphes
            para_break_start = start + (effective_max // 2)
            logger.debug(
                f"para_break_start: {para_break_start} (type: {type(para_break_start).__name__})"
            )

            para_break = text.rfind("\n\n", para_break_start, end)
            logger.debug(
                f"para_break trouvé: {para_break} (type: {type(para_break).__name__})"
            )

            min_break_pos = start + (effective_max // 3)
            logger.debug(
                f"min_break_pos: {min_break_pos} (type: {type(min_break_pos).__name__})"
            )

            if para_break > min_break_pos and para_break != -1:
                # ⚠️ Conversion explicite en entier avant addition
                para_break = int(para_break)
                end = para_break + 2
                logger.debug(f"Fin de paragraphe trouvée, end devient: {end}")
            else:
                # Chercher en arrière un point de fin de phrase
                sentence_found = False
                for punct in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
                    sentence_break_start = start + (effective_max // 2)
                    sentence_break = text.rfind(punct, sentence_break_start, end)
                    logger.debug(
                        f"Recherche de '{punct}': sentence_break={sentence_break}"
                    )

                    if sentence_break > min_break_pos and sentence_break != -1:
                        # ⚠️ Conversion explicite en entier avant addition
                        sentence_break = int(sentence_break)
                        punct_len = len(punct)
                        end = sentence_break + punct_len
                        sentence_found = True
                        logger.debug(f"Fin de phrase trouvée, end devient: {end}")
                        break

        # Garantir que start et end sont des entiers valides
        start_idx = int(start)
        end_idx = int(end)
        logger.debug(f"Indices finaux: start_idx={start_idx}, end_idx={end_idx}")

        # Extraire le chunk et vérifier sa cohérence
        try:
            chunk_text = text[start_idx:end_idx].strip()
            logger.debug(f"Chunk extrait de longueur: {len(chunk_text)}")
        except Exception as e:
            logger.error(
                f"ERREUR extraction chunk: {e}, indices: [{start_idx}:{end_idx}]",
                exc_info=True,
            )
            # Fallback en cas d'erreur d'indices
            start = start_idx + 1
            continue

        if not chunk_text:
            # Avancer au prochain caractère non-vide
            try:
                next_non_empty = text.find(r"\S", start_idx)
                logger.debug(f"Chunk vide, recherche de non-vide: {next_non_empty}")
                start = next_non_empty if next_non_empty > 0 else end_idx
                continue
            except Exception as e:
                logger.error(f"ERREUR recherche non-vide: {e}", exc_info=True)
                start = start_idx + 1
                continue

        # Ajouter le chunk à la liste
        try:
            chunks.append(
                {
                    "content": chunk_text,
                    "start_char": base_offset + start_idx,
                    "end_char": base_offset + end_idx,
                }
            )
            chunk_count += 1
            logger.debug(f"Chunk #{chunk_count} ajouté")
        except Exception as e:
            logger.error(f"ERREUR ajout chunk: {e}", exc_info=True)
            break

        # Adapter l'overlap intelligemment
        if end < len(text):
            try:
                # Utiliser uniquement des opérations entières
                overlap_start = end - (effective_overlap * 2)
                overlap_start = int(overlap_start)  # Conversion explicite
                overlap_end = int(end)

                logger.debug(
                    f"Calcul overlap: start={overlap_start}, end={overlap_end}"
                )

                # Vérifier les limites
                if overlap_start < 0:
                    overlap_start = 0

                # Recherche des positions de séparation naturelles
                overlap_positions = []
                for punct in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
                    pos = text.rfind(punct, overlap_start, overlap_end)
                    logger.debug(f"Position '{punct}': {pos}")
                    if pos != -1:
                        overlap_positions.append(pos)

                # Trouver la meilleure position d'overlap
                if overlap_positions:
                    overlap_pos = max(overlap_positions)
                    logger.debug(f"Meilleure position overlap: {overlap_pos}")
                else:
                    overlap_pos = -1
                    logger.debug("Aucune position d'overlap trouvée")

                # Calculer la position minimum acceptable
                min_overlap_pos = end - (effective_overlap * 2)
                min_overlap_pos = int(min_overlap_pos)  # Conversion explicite

                # Déterminer la position de départ du prochain chunk
                if (
                    overlap_pos > start
                    and overlap_pos > min_overlap_pos
                    and overlap_pos != -1
                ):
                    next_start = overlap_pos + 2
                else:
                    next_start = max(start + 1, end - effective_overlap)

                next_start = int(next_start)  # Conversion explicite finale
                logger.debug(f"Position de départ du prochain chunk: {next_start}")
            except Exception as e:
                logger.error(f"ERREUR calcul overlap: {e}", exc_info=True)
                # Fallback en cas d'erreur: avancer simplement
                next_start = int(end)
        else:
            next_start = int(end)

        start = next_start
        logger.debug(f"Fin d'itération, start mis à jour: {start}")

    logger.debug(f"Fin de _create_semantic_chunks: {len(chunks)} chunks générés")
    return chunks
