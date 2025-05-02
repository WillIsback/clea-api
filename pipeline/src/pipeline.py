import os
from typing import Dict, Any, Optional

from doc_loader.src import DocsLoader
from vectordb import (
    add_document_with_chunks,
    get_db,
)


def process_and_store(
    file_path: str,
    max_length: int = 500,
    overlap: int = 100,
    theme: Optional[str] = "Thème générique",
    corpus_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Traite un fichier et l'insère dans la base de données avec une structure hiérarchique.

    Cette fonction effectue l'extraction du texte, la segmentation hiérarchique
    et l'insertion en base de données avec gestion des embeddings.

    Args:
        file_path: Chemin du fichier à traiter.
        max_length: Taille maximale d'un chunk final. Par défaut à 500 caractères.
        overlap: Chevauchement entre les chunks. Par défaut à 100 caractères.
        theme: Thème à appliquer au document. Par défaut "Thème générique".
        document_type: Type du document (déterminé automatiquement si None).
        corpus_id: Identifiant du corpus (généré automatiquement si None).

    Returns:
        Dict[str, Any]: Résultat de l'opération avec l'ID du document et les statistiques.

    Raises:
        FileNotFoundError: Si le fichier spécifié n'existe pas.
        ValueError: Si aucun contenu n'a pu être extrait du document ou si une erreur
                   survient lors de l'insertion en base.
    """
    # Vérifier que le fichier existe
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Le fichier {file_path} n'existe pas.")

    # Étape 1: Extraction du texte complet (conversion de l'itérateur en liste)
    docs_witch_chunks = DocsLoader(file_path).extract_documents(max_length=max_length)
    if not docs_witch_chunks:
        raise ValueError("Aucun contenu extrait du document.")
    if theme:
        docs_witch_chunks.document.theme = theme

    # Étape 2: Insertion en base de données
    db = next(get_db())
    try:
        docs_dict = docs_witch_chunks.to_dict()
        result = add_document_with_chunks(
            db, docs_witch_chunks.document, docs_dict["chunks"]
        )
        return result
    except Exception as e:
        db.rollback()
        raise ValueError(f"Erreur lors de l'insertion en base de données: {str(e)}")


def determine_document_type(file_path: str) -> str:
    """Détermine le type de document à partir du chemin du fichier.

    Args:
        file_path: Chemin complet vers le fichier.

    Returns:
        Type de document détecté en fonction de l'extension.
    """
    extension = os.path.splitext(file_path.lower())[1]

    type_map = {
        ".pdf": "PDF",
        ".txt": "TXT",
        ".md": "MARKDOWN",
        ".doc": "WORD",
        ".docx": "WORD",
        ".html": "HTML",
        ".htm": "HTML",
        ".xml": "XML",
        ".csv": "CSV",
        ".json": "JSON",
        ".ppt": "POWERPOINT",
        ".pptx": "POWERPOINT",
        ".xls": "EXCEL",
        ".xlsx": "EXCEL",
    }

    return type_map.get(extension, "UNKNOWN")
