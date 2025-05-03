"""
Constantes utilisées par les modules de segmentation.

Ce module définit les limites et paramètres pour la segmentation des documents.
"""

THRESHOLD_LARGE = 5_000_000  # > 5 Mo  →  mode « stream »
MAX_CHUNKS = 5000  # Augmenté de 2000 à 5000 pour les corpus volumineux
MAX_TEXT_LENGTH = 20_000_000  # Augmenté de 10Mo à 20Mo en caractères
MAX_CHUNK_SIZE = 8_000  # Réduit de 10000 à 8000 pour des chunks plus précis
MIN_LEVEL3_LENGTH = 200  # Réduit de 300 à 200 pour permettre plus de chunks fins
MAX_LEVEL3_CHUNKS = 100  # Augmenté de 50 à 100 chunks niveau 3 par paragraphe
