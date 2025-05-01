from doc_loader.src import DocsLoader, ExtractedDocument
from vectordb.src.database import DocumentCreate, add_documents
from typing import List


class InterfaceDocument:
    """
    Interface pour convertir une liste de documents extraits (ExtractedDocument)
    en une liste de documents à créer (DocumentCreate).
    """

    @staticmethod
    def extract_to_create(docs: List[ExtractedDocument]) -> List[DocumentCreate]:
        """
        Convertit une liste de documents extraits en une liste de documents à créer.

        Args:
            docs (List[ExtractedDocument]): Liste des documents extraits.

        Returns:
            List[DocumentCreate]: Liste des documents à créer.
        """
        return [
            DocumentCreate(
                title=doc.title,
                content=doc.content,
                theme=doc.theme,
                document_type=doc.document_type,
                publish_date=doc.publish_date,  # Assurez-vous que publish_date est déjà au format ISO
            )
            for doc in docs
        ]


def process_and_store(
    file_path: str, max_length: int = 1000, theme: str = "Thème générique"
):
    """
    Charge un fichier, extrait les documents, et les insère dans la base de données.

    Args:
        file_path (str): Chemin du fichier à traiter.
        max_length (int): Taille maximale d'un chunk.
        theme (str): Thème à appliquer aux documents.

    Returns:
        List[DocumentCreate]: Liste des documents ajoutés avec leurs IDs.
    """
    # Étape 1 : Extraction des documents
    loader = DocsLoader(file_path)
    docs = list(loader.extract_documents(max_length=max_length))

    if not docs:
        raise ValueError("Aucun contenu extrait du document.")

    # Appliquer le thème spécifié
    if theme != "Thème générique":
        for doc in docs:
            doc.theme = theme

    # Étape 2 : Conversion des documents extraits en documents à créer
    interface = InterfaceDocument()
    documents_to_create = interface.extract_to_create(docs)

    # Étape 3 : Ajouter les documents à la base de données
    return add_documents(documents_to_create)
