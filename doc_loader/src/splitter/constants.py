"""
Constantes utilisées par les modules de segmentation.

Ce module définit les limites et paramètres pour la segmentation des documents.
"""

THRESHOLD_LARGE = 5_000_000  # > 5 Mo  →  mode « stream »
MAX_CHUNKS = 500  # Limite maximale de chunks générés
MAX_TEXT_LENGTH = 10_000_000  # ~10Mo en caractères
MAX_CHUNK_SIZE = 10_000  # Taille maximale d'un chunk
MIN_LEVEL3_LENGTH = 300  # Taille minimale pour un chunk de niveau 3
MAX_LEVEL3_CHUNKS = 10  # Nombre max de chunks de niveau 3 par paragraphe
