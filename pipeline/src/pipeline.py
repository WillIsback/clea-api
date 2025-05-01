import os
import uuid
from pathlib import Path
from datetime import date, datetime
from typing import Dict, List, Any, Optional, Tuple

from doc_loader.src import DocsLoader, ExtractedDocument
from doc_loader.src.data_extractor.base import adaptive_segmentation
from vectordb.src.database import (
    DocumentCreate,
    add_document_with_chunks,
    get_db,
    Session
)


class InterfaceDocument:
    """Interface pour convertir une liste de documents extraits en documents à créer.
    
    Cette classe fournit des méthodes statiques pour transformer les documents
    extraits par le DocsLoader en format compatible avec la base de données.
    """

    @staticmethod
    def extract_to_create(docs: List[ExtractedDocument]) -> List[DocumentCreate]:
        """Convertit une liste de documents extraits en une liste de documents à créer.

        Args:
            docs: Liste des documents extraits par le DocsLoader.

        Returns:
            Liste des documents formatés pour insertion en base de données.
        """
        return [
            DocumentCreate(
                title=doc.title,
                theme=doc.theme,
                document_type=doc.document_type,
                publish_date=doc.publish_date,
            )
            for doc in docs
        ]

    @staticmethod
    def convert_to_hierarchical_chunks(docs: List[ExtractedDocument], max_length: int = 500) -> Tuple[DocumentCreate, List[Dict[str, Any]]]:
        """Convertit des documents extraits en un document avec chunks hiérarchiques.
        
        Utilise le texte des documents extraits pour générer une structure hiérarchique
        de chunks adaptée à la nouvelle structure de la base de données.

        Args:
            docs: Liste des documents extraits.
            max_length: Taille maximale souhaitée pour les chunks de niveau final.

        Returns:
            Un tuple contenant:
                - Le document principal à créer avec ses métadonnées
                - Une liste de chunks avec leur structure hiérarchique
        """
        if not docs:
            raise ValueError("Aucun document fourni pour la conversion.")
        
        # Extraire les métadonnées du premier document pour le document principal
        main_doc = DocumentCreate(
            title=docs[0].title,
            theme=docs[0].theme,
            document_type=docs[0].document_type,
            publish_date=docs[0].publish_date,
            corpus_id=None  # Sera généré automatiquement par add_document_with_chunks
        )
        
        # Concaténer le contenu de tous les documents extraits
        full_text = "\n\n".join(doc.content for doc in docs if doc.content)
        
        # Générer les chunks hiérarchiques avec adaptive_segmentation
        chunks, _ = adaptive_segmentation(
            text=full_text,
            max_length=max_length,
            overlap=int(max_length * 0.2)
        )
        
        return main_doc, chunks


def process_document(file_path: str) -> str:
    """Extrait le contenu textuel d'un document.

    Args:
        file_path: Chemin vers le fichier à traiter.

    Returns:
        Le contenu textuel extrait du document.

    Raises:
        ValueError: Si aucun contenu n'a pu être extrait.
    """
    loader = DocsLoader(file_path)
    docs = list(loader.extract_documents(max_length=10000))  # Grande taille pour obtenir le document complet

    if not docs:
        raise ValueError("Aucun contenu extrait du document.")
    
    # Concaténer tout le contenu extrait
    return "\n\n".join(doc.content for doc in docs if doc.content)


def process_and_store(
    file_path: str, 
    max_length: int = 500,
    overlap: int = 100,
    theme: Optional[str] = "Thème générique",
    document_type: Optional[str] = None,
    corpus_id: Optional[str] = None
) -> Dict[str, Any]:
    """Traite un fichier et l'insère dans la base de données avec une structure hiérarchique.

    Cette fonction effectue l'extraction du texte, la segmentation hiérarchique
    et l'insertion en base de données avec gestion des embeddings.

    Args:
        file_path: Chemin du fichier à traiter.
        max_length: Taille maximale d'un chunk final.
        overlap: Chevauchement entre les chunks.
        theme: Thème à appliquer au document.
        document_type: Type du document (déterminé automatiquement si None).
        corpus_id: Identifiant du corpus (généré si None).

    Returns:
        Résultat de l'opération avec l'ID du document et les statistiques.

    Raises:
        ValueError: Si aucun contenu n'a pu être extrait du document.
    """
    # Vérifier que le fichier existe
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Le fichier {file_path} n'existe pas.")
    
    # Déterminer le type de document si non spécifié
    if not document_type:
        document_type = determine_document_type(file_path)

    # Étape 1: Extraction du texte complet
    full_text = process_document(file_path)
    
    if not full_text:
        raise ValueError("Aucun contenu extrait du document.")
    
    # Étape 2: Segmentation hiérarchique du texte
    chunks, stats = adaptive_segmentation(
        text=full_text,
        max_length=max_length,
        overlap=overlap
    )
    
    # Étape 3: Création de l'objet DocumentCreate
    doc_data = DocumentCreate(
        title=Path(file_path).stem,
        theme=theme or "Thème générique",
        document_type=document_type,
        publish_date=date.today(),
        corpus_id=corpus_id
    )
    
    # Étape 4: Insertion en base de données
    db = next(get_db())
    try:
        result = add_document_with_chunks(db, doc_data, chunks)
        
        # Ajouter les statistiques de segmentation au résultat
        result.update({
            "segmentation_stats": stats,
            "file_path": file_path
        })
        
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
        '.pdf': 'PDF',
        '.txt': 'TXT',
        '.md': 'MARKDOWN',
        '.doc': 'WORD',
        '.docx': 'WORD',
        '.html': 'HTML',
        '.htm': 'HTML',
        '.xml': 'XML',
        '.csv': 'CSV',
        '.json': 'JSON',
        '.ppt': 'POWERPOINT',
        '.pptx': 'POWERPOINT',
        '.xls': 'EXCEL',
        '.xlsx': 'EXCEL',
    }
    
    return type_map.get(extension, "UNKNOWN")