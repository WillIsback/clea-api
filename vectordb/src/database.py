from sqlalchemy import create_engine, Integer, String, Text, Date
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column, declarative_base
from sqlalchemy.sql import text
from .embeddings import EmbeddingGenerator
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import List, Optional
import json

load_dotenv()

# Configuration de la base de données
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "vectordb")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Création du moteur SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DocumentCreate(BaseModel):
    """
    Classe représentant un document à créer.

    :param title: Titre du document.
    :type title: str
    :param content: Contenu du document.
    :type content: str
    :param theme: Thème du document.
    :type theme: str
    :param document_type: Type de document.
    :type document_type: str
    :param publish_date: Date de publication du document.
    :type publish_date: date
    """

    title: str
    content: str
    theme: str
    document_type: str
    publish_date: date


class DocumentResponse(BaseModel):
    """
    @brief Classe représentant un document de réponse.
    @details Contient les informations du document ainsi que son ID.
    @structure:
        - id (int): ID du document.
        - title (str): Titre du document.
        - content (str): Contenu du document.
        - theme (str): Thème du document.
        - document_type (str): Type de document.
        - publish_date (date): Date de publication du document.
    """

    id: int
    title: str
    content: str
    theme: str
    document_type: str
    publish_date: date

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    """
    @brief Classe représentant un document à mettre à jour.
    @details Contient les informations nécessaires pour mettre à jour un document.
    @structure:
        - document_id (int): ID du document à mettre à jour.
        - title (str, optional): Nouveau titre.
        - content (str, optional): Nouveau contenu.
        - theme (str, optional): Nouveau thème.
        - document_type (str, optional): Nouveau type de document.
        - publish_date (str, optional): Nouvelle date de publication (format ISO).
    """

    document_id: int = Field(
        ..., description="Identifiant unique du document à mettre à jour"
    )
    title: Optional[str] = Field(None, description="Titre mis à jour du document")
    content: Optional[str] = Field(None, description="Contenu mis à jour du document")
    theme: Optional[str] = Field(None, description="Thème mis à jour du document")
    document_type: Optional[str] = Field(
        None, description="Type mis à jour du document"
    )
    publish_date: Optional[date] = Field(
        None, description="Date de publication mise à jour (format ISO)"
    )


# Modèle pour les documents
class Document(Base):
    """
    @class Document
    @brief Modèle SQLAlchemy représentant un document dans la base de données.
    @structure:
        - id (int): Identifiant unique du document.
        - title (str): Titre du document.
        - content (str): Contenu du document.
        - theme (str): Thème du document.
        - document_type (str): Type de document.
        - publish_date (date): Date de publication du document.
        - embedding (Text): Représentation vectorielle du contenu du document.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    theme: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    publish_date: Mapped[date] = mapped_column(Date, nullable=False)
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# Fonction pour obtenir une session de base de données
def get_db():
    """
    @brief Fonction pour obtenir une session de base de données.
    @return Générateur de session de base de données.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Fonction pour initialiser la base de données
def init_db():
    """
    @brief Fonction pour initialiser la base de données.
    Crée les tables définies dans les modèles SQLAlchemy.
    """
    Base.metadata.create_all(bind=engine)
    print("Base de données initialisée avec succès.")


##############################################################
#  Fonction helper
##############################################################


def add_documents(documents: List[DocumentCreate]):
    """
    Ajoute une liste de documents à la base de données et génère leurs embeddings.

    Args:
        documents (List[DocumentCreate]): Liste de documents à ajouter.

    Returns:
        dict: Résultat de l'opération avec les IDs des documents ajoutés ou les erreurs rencontrées.
    """
    embedding_generator = EmbeddingGenerator()
    db = next(get_db())
    results = {"added": [], "errors": []}

    for doc_data in documents:
        try:
            # Vérifier si le document existe déjà (basé sur le titre)
            existing = (
                db.query(Document).filter(Document.title == doc_data.title).first()
            )
            if existing:
                print(f"Document '{doc_data.title}' existe déjà, ignoré.")
                results["errors"].append(
                    {"title": doc_data.title, "error": "Document already exists"}
                )
                continue

            # Vérifier que le contenu n'est pas vide
            if not doc_data.content or not doc_data.content.strip():
                print(f"Le contenu du document '{doc_data.title}' est vide, ignoré.")
                results["errors"].append(
                    {"title": doc_data.title, "error": "Content is empty"}
                )
                continue

            # Créer un nouveau document
            document = Document(
                title=doc_data.title,
                content=doc_data.content,
                theme=doc_data.theme,
                document_type=doc_data.document_type,
                publish_date=doc_data.publish_date,
            )

            db.add(document)
            db.commit()
            db.refresh(document)

            # Générer et stocker l'embedding
            embedding = embedding_generator.generate_embedding(doc_data.content)
            db.execute(
                text("UPDATE documents SET embedding = :embedding WHERE id = :id"),
                {"embedding": json.dumps(embedding), "id": document.id},
            )
            db.commit()

            print(
                f"Document '{doc_data.title}' ajouté avec succès (ID: {document.id})."
            )
            results["added"].append(
                {
                    "id": document.id,
                    "title": doc_data.title,
                    "content": doc_data.content,
                    "theme": doc_data.theme,
                    "document_type": doc_data.document_type,
                    "publish_date": doc_data.publish_date,
                }
            )

        except Exception as e:
            print(f"Erreur lors de l'ajout du document '{doc_data.title}': {e}")
            db.rollback()
            results["errors"].append({"title": doc_data.title, "error": str(e)})

    return results


def delete_document(document_id: int):
    """
    Supprime un document de la base de données.

    Args:
        document_id (int): ID du document à supprimer.

    Returns:
        dict: Résultat de l'opération.
    """
    db = next(get_db())
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"error": f"Document avec ID {document_id} introuvable."}

        db.delete(document)
        db.commit()
        print(f"Document avec ID {document_id} supprimé avec succès.")
        return {"success": f"Document avec ID {document_id} supprimé avec succès."}
    except Exception as e:
        db.rollback()
        print(f"Erreur lors de la suppression du document avec ID {document_id}: {e}")
        return {"error": str(e)}


def update_document(document_update: DocumentUpdate):
    """
    Met à jour un document existant dans la base de données.

    Args:
        document_update (DocumentUpdate): Objet contenant les champs à mettre à jour.

    Returns:
        dict: Résultat de l'opération.
    """
    db = next(get_db())
    try:
        document = (
            db.query(Document)
            .filter(Document.id == document_update.document_id)
            .first()
        )
        if not document:
            return {
                "error": f"Document avec ID {document_update.document_id} introuvable."
            }

        # Mettre à jour les champs spécifiés
        if document_update.title is not None:
            document.title = document_update.title
        if document_update.content is not None:
            document.content = document_update.content
        if document_update.theme is not None:
            document.theme = document_update.theme
        if document_update.document_type is not None:
            document.document_type = document_update.document_type
        if document_update.publish_date is not None:
            # Vérifier si publish_date est déjà un objet datetime.date
            if isinstance(document_update.publish_date, str):
                document.publish_date = datetime.strptime(
                    document_update.publish_date, "%Y-%m-%d"
                )
            else:
                document.publish_date = document_update.publish_date

        db.commit()
        db.refresh(document)
        print(f"Document avec ID {document_update.document_id} mis à jour avec succès.")

        # Retourner le document mis à jour sous forme de dictionnaire
        return {
            "id": document.id,
            "title": document.title,
            "content": document.content,
            "theme": document.theme,
            "document_type": document.document_type,
            "publish_date": document.publish_date,
        }
    except Exception as e:
        db.rollback()
        print(
            f"Erreur lors de la mise à jour du document avec ID {document_update.document_id}: {e}"
        )
        return {"error": str(e)}
