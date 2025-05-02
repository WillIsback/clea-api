"""
Utilitaires pour le traitement et l'analyse de texte.

Ce module fournit des fonctions d'aide pour:
- Extraire des résumés significatifs de texte
- Détecter des phrases clés
- Manipuler des portions de texte
"""

import re


def _get_meaningful_preview(text: str, max_length: int) -> str:
    """
    Extrait un aperçu significatif d'un texte, en privilégiant le début mais en capturant
    aussi quelques éléments importants.

    Args:
        text: Texte d'entrée.
        max_length: Longueur maximale de l'aperçu.

    Returns:
        str: Aperçu significatif du texte.
    """
    if len(text) <= max_length:
        return text

    # Prendre le premier tiers de max_length au début
    start_portion = text[: max_length // 3].strip()

    # Extraire des phrases clés du milieu (détection basique)
    middle_text = text[len(text) // 3 : 2 * len(text) // 3]
    middle_sentences = re.split(r"[.!?]\s+", middle_text)
    important_middle = ""

    # Sélection de phrases potentiellement importantes
    for sentence in middle_sentences:
        if any(
            marker in sentence.lower()
            for marker in ["important", "essentiel", "clé", "crucial", "principal"]
        ):
            important_middle += sentence + ". "
            if len(important_middle) > max_length // 6:
                break

    # Prendre une portion à la fin
    end_portion = text[-max_length // 6 :].strip()

    # Combiner les portions avec des indicateurs
    result = start_portion

    if important_middle:
        result += "\n[...]\n" + important_middle

    if len(start_portion) + len(important_middle) + len(end_portion) + 20 <= max_length:
        result += "\n[...]\n" + end_portion

    return result


def is_sentence_boundary(text: str, pos: int) -> bool:
    """
    Détermine si une position dans le texte correspond à une fin de phrase.

    Args:
        text: Le texte à analyser.
        pos: La position potentielle de fin de phrase.

    Returns:
        bool: True si la position est une fin de phrase, False sinon.
    """
    if pos <= 0 or pos >= len(text):
        return False

    # Vérifier si c'est une ponctuation de fin
    if text[pos - 1] in ".!?":
        # Vérifier le caractère suivant (espace, retour à la ligne ou fin de texte)
        if pos == len(text) or text[pos] in " \n\t":
            return True

    return False


def find_paragraph_boundaries(text: str) -> list:
    """
    Trouve les frontières de paragraphes dans un texte.

    Args:
        text: Le texte à analyser.

    Returns:
        list: Liste des positions de début de paragraphe.
    """
    boundaries = [0]  # Le texte commence toujours par un paragraphe

    # Recherche des séquences de saut de ligne qui séparent les paragraphes
    for match in re.finditer(r"\n\s*\n", text):
        boundaries.append(match.end())

    return boundaries
