import logging
import os
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    insert,
    text,
)
from sqlalchemy.orm import (
    Session,
    declarative_base,
    mapped_column,
    relationship,
    sessionmaker,
)

from .embeddings import EmbeddingGenerator


load_dotenv()

# Configuration de la base de données
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "vectordb")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

logger = logging.getLogger(__name__)

# Création du moteur SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DocumentCreate(BaseModel):
    """Modèle pour la création d'un document.

    Args:
        title: Titre du document.
        theme: Thème du document.
        document_type: Type du document (PDF, TXT, etc.).
        publish_date: Date de publication du document.
        corpus_id: Identifiant du corpus auquel appartient le document.
    """

    title: str
    theme: str
    document_type: str
    publish_date: date
    corpus_id: Optional[str] = None


class ChunkCreate(BaseModel):
    """Modèle pour la création d'un chunk de document.

    Args:
        content: Contenu textuel du chunk.
        start_char: Position de début dans le document source.
        end_char: Position de fin dans le document source.
        hierarchy_level: Niveau hiérarchique (0: document, 1: section, 2: paragraphe, 3: chunk).
        parent_chunk_id: ID du chunk parent dans la hiérarchie (si applicable).
    """

    content: str
    start_char: int
    end_char: int
    hierarchy_level: int = 3  # Par défaut: chunk de base
    parent_chunk_id: Optional[int] = None


class DocumentResponse(BaseModel):
    """Modèle de réponse pour un document.

    Args:
        id: ID unique du document.
        title: Titre du document.
        theme: Thème du document.
        document_type: Type du document.
        publish_date: Date de publication.
        corpus_id: Identifiant du corpus.
        chunk_count: Nombre de chunks associés.
    """

    id: int
    title: str
    theme: str
    document_type: str
    publish_date: date
    corpus_id: Optional[str] = None
    chunk_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    """Modèle pour la mise à jour d'un document.

    Args:
        document_id: ID du document à mettre à jour.
        title: Nouveau titre (optionnel).
        theme: Nouveau thème (optionnel).
        document_type: Nouveau type de document (optionnel).
        publish_date: Nouvelle date de publication (optionnel).
        corpus_id: Nouvel identifiant de corpus (optionnel).
    """

    document_id: int = Field(
        ..., description="Identifiant unique du document à mettre à jour"
    )
    title: Optional[str] = Field(None, description="Titre mis à jour du document")
    theme: Optional[str] = Field(None, description="Thème mis à jour du document")
    document_type: Optional[str] = Field(
        None, description="Type mis à jour du document"
    )
    publish_date: Optional[date] = Field(
        None, description="Date de publication mise à jour (format ISO)"
    )
    corpus_id: Optional[str] = Field(None, description="Identifiant du corpus")


# Modèle pour les documents
class Document(Base):
    """Modèle SQLAlchemy pour la table des documents.

    Stocke les métadonnées globales des documents sans leur contenu.
    """

    __tablename__ = "documents"

    id = mapped_column(Integer, primary_key=True)
    title = mapped_column(String(255), nullable=False)
    theme = mapped_column(String(100))
    document_type = mapped_column(String(100))
    publish_date = mapped_column(Date)
    corpus_id = mapped_column(
        String(36), index=True
    )  # UUID stocké sous forme de chaîne
    created_at = mapped_column(Date, default=datetime.now)

    # Relation avec les chunks
    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    # Index sur les colonnes fréquemment utilisées pour le filtrage
    __table_args__ = (
        Index("idx_document_theme", "theme"),
        Index("idx_document_type", "document_type"),
        Index("idx_document_date", "publish_date"),
        Index("idx_document_corpus", "corpus_id"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = mapped_column(Integer, primary_key=True)
    document_id = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(768))
    start_char = mapped_column(Integer)
    end_char = mapped_column(Integer)
    hierarchy_level = mapped_column(Integer, default=3)
    parent_chunk_id = mapped_column(
        Integer, ForeignKey("chunks.id", ondelete="CASCADE")
    )

    # relations ----------------------------------------------------------------
    document = relationship("Document", back_populates="chunks")

    parent = relationship(  # 1 parent  ←  N children
        "Chunk",
        remote_side=[id],
        back_populates="children",
    )
    children = relationship(
        "Chunk",
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True,  #  ✅ indispensable !
    )

    __table_args__ = (
        Index("idx_chunk_document_level", "document_id", "hierarchy_level"),
        Index("idx_chunk_parent", "parent_chunk_id"),
    )


# Configuration pour basculer entre différents types d'index
class IndexConfig(Base):
    """Modèle SQLAlchemy pour la configuration des index.

    Stocke les paramètres de configuration pour les index vectoriels par corpus.
    """

    __tablename__ = "index_configs"

    id = mapped_column(Integer, primary_key=True)
    corpus_id = mapped_column(String(36), unique=True, nullable=False)
    index_type = mapped_column(String(20), default="ivfflat")  # 'ivfflat' ou 'hnsw'
    is_indexed = mapped_column(Boolean, default=False)
    chunk_count = mapped_column(Integer, default=0)
    last_indexed = mapped_column(Date, nullable=True)

    # Configuration spécifique aux index
    ivf_lists = mapped_column(Integer, default=100)
    hnsw_m = mapped_column(Integer, default=16)
    hnsw_ef_construction = mapped_column(Integer, default=200)


# Fonction pour obtenir une session de base de données
def get_db():
    """Crée et retourne une session de base de données.

    Yields:
        Session: Session SQLAlchemy à utiliser pour les opérations de base de données.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Fonction pour initialiser la base de données
def init_db():
    """Initialise la base de données avec les tables et extensions nécessaires.

    Crée l'extension pgvector et les tables définies dans les modèles SQLAlchemy.
    """
    # Créer l'extension pgvector si elle n'existe pas déjà
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Créer les tables
    Base.metadata.create_all(bind=engine)
    print("Base de données initialisée avec succès.")


def create_index_for_corpus(corpus_id, index_type="ivfflat", force=False):
    """Crée un index vectoriel pour un corpus spécifique.

    Args:
        corpus_id: Identifiant du corpus.
        index_type: Type d'index ('ivfflat' ou 'hnsw').
        force: Si True, recréera l'index même s'il existe déjà.

    Returns:
        dict: Résultat de l'opération.
    """
    db = next(get_db())
    try:
        # Vérifier si le corpus existe déjà avec un index
        config = (
            db.query(IndexConfig).filter(IndexConfig.corpus_id == corpus_id).first()
        )

        # Compter le nombre de chunks dans ce corpus
        chunk_count = (
            db.query(Chunk)
            .join(Document)
            .filter(Document.corpus_id == corpus_id)
            .count()
        )

        # Si aucune configuration n'existe, en créer une nouvelle
        if not config:
            # Sélectionner automatiquement le type d'index en fonction du nombre de chunks
            if index_type == "auto":
                index_type = "hnsw" if chunk_count > 300000 else "ivfflat"

            config = IndexConfig(
                corpus_id=corpus_id, index_type=index_type, chunk_count=chunk_count
            )
            db.add(config)
            db.flush()
        else:
            # Mettre à jour le nombre de chunks
            config.chunk_count = chunk_count

            # Si force=True ou si le type d'index doit changer, mettre à jour
            if force or (index_type != "auto" and config.index_type != index_type):
                # Supprimer l'ancien index s'il existe
                if config.is_indexed:
                    try:
                        if config.index_type == "ivfflat":
                            db.execute(
                                text(
                                    f"DROP INDEX IF EXISTS chunks_embedding_ivfflat_{corpus_id.replace('-', '_')}"
                                )
                            )
                        else:
                            db.execute(
                                text(
                                    f"DROP INDEX IF EXISTS chunks_embedding_hnsw_{corpus_id.replace('-', '_')}"
                                )
                            )
                    except Exception as e:
                        print(f"Erreur lors de la suppression de l'ancien index: {e}")

                # Mettre à jour le type d'index si nécessaire
                if index_type != "auto" and config.index_type != index_type:
                    config.index_type = index_type

        # Créer l'index approprié
        if config.index_type == "ivfflat":
            index_name = f"chunks_embedding_ivfflat_{corpus_id.replace('-', '_')}"
            sql = f"""
            CREATE INDEX {index_name}
            ON chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {config.ivf_lists})
            WHERE id IN (SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.corpus_id = :corpus_id)
            """
        else:  # hnsw
            index_name = f"chunks_embedding_hnsw_{corpus_id.replace('-', '_')}"
            sql = f"""
            CREATE INDEX {index_name}
            ON chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = {config.hnsw_m}, ef_construction = {config.hnsw_ef_construction})
            WHERE id IN (SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.corpus_id = :corpus_id)
            """

        try:
            db.execute(text(sql), {"corpus_id": corpus_id})
            config.is_indexed = True
            config.last_indexed = datetime.now()
            db.commit()
            return {
                "success": f"Index {config.index_type} créé avec succès pour le corpus {corpus_id}"
            }
        except Exception as e:
            db.rollback()
            return {"error": f"Échec de création de l'index: {str(e)}"}

    except Exception as e:
        db.rollback()
        return {"error": f"Erreur lors de la gestion de l'index: {str(e)}"}


##############################################################
#  Fonction helper
##############################################################


def add_document_with_chunks(
    db: Session, doc: DocumentCreate, chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Ajoute un document et ses chunks à la base de données.

    Args:
        db: Session de base de données.
        doc: Données du document à créer.
        chunks: Liste des chunks avec leur contenu et métadonnées.

    Returns:
        Dict[str, Any]: Résultat de l'opération avec l'ID du document et des informations sur les chunks.
    """
    # Générer un corpus_id si non fourni
    if not doc.corpus_id:
        doc.corpus_id = str(uuid.uuid4())

    # Créer le document
    document = Document(**doc.model_dump())
    db.add(document)
    db.flush()  # Récupérer document.id

    # Préparer l'embedding generator
    eg = EmbeddingGenerator()
    bulk_rows = []
    id_map = {}

    # Génération des embeddings et mapping des relations parent-enfant
    for c in chunks:
        # Générer l'embedding pour le chunk
        emb = eg.generate_embedding(c["content"])

        # Préparer la ligne pour insertion en bulk
        chunk_data = {
            "document_id": document.id,
            "content": c["content"],
            "embedding": emb,
            "start_char": c.get("start_char", 0),
            "end_char": c.get("end_char", len(c["content"])),
            "hierarchy_level": c.get("hierarchy_level", 3),
            "parent_chunk_id": id_map.get(c.get("parent_id")),
        }

        bulk_rows.append(chunk_data)

        # Mémoriser l'ID temporaire pour les relations parent-enfant
        if "id" in c:
            id_map[c["id"]] = len(id_map) + 1  # temp key → index in bulk_rows

    # Insérer tous les chunks en une seule opération
    if bulk_rows:
        db.execute(insert(Chunk), bulk_rows)

    # Gérer la configuration d'index pour ce corpus
    cfg = db.query(IndexConfig).filter(IndexConfig.corpus_id == doc.corpus_id).first()
    if not cfg:
        # Créer une nouvelle configuration d'index
        db.add(
            IndexConfig(
                corpus_id=doc.corpus_id, index_type="ivfflat", chunk_count=len(chunks)
            )
        )
        create_index_needed = True
    else:
        # Mettre à jour la configuration existante
        cfg.chunk_count += len(chunks)
        create_index_needed = False

        # Recommander un changement d'index si nécessaire
        if cfg.chunk_count > 300_000 and cfg.index_type == "ivfflat":
            logger.warning(
                "Corpus %s contient désormais %s chunks, envisager la migration vers un index HNSW",
                doc.corpus_id,
                cfg.chunk_count,
            )

    # Valider la transaction
    db.commit()

    # Retourner le résultat
    return {
        "document_id": document.id,
        "chunks": len(chunks),
        "corpus_id": doc.corpus_id,
        "create_index": create_index_needed,
    }


def update_document_with_chunks(
    document_update: DocumentUpdate, new_chunks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Met à jour un document existant et ses chunks dans la base de données.

    Args:
        document_update: Données de mise à jour du document.
        new_chunks: Nouveaux chunks à ajouter ou à remplacer (si replace_chunks=True).

    Returns:
        Dict[str, Any]: Résultat de l'opération avec les informations mises à jour.
    """
    db = next(get_db())
    try:
        # Trouver le document à mettre à jour
        document = (
            db.query(Document)
            .filter(Document.id == document_update.document_id)
            .first()
        )
        if not document:
            return {
                "error": f"Document avec ID {document_update.document_id} introuvable."
            }

        # Sauvegarder l'ancien corpus_id pour vérifier s'il change
        old_corpus_id = document.corpus_id

        # Mettre à jour les champs spécifiés du document
        if document_update.title is not None:
            document.title = document_update.title
        if document_update.theme is not None:
            document.theme = document_update.theme
        if document_update.document_type is not None:
            document.document_type = document_update.document_type
        if document_update.publish_date is not None:
            if isinstance(document_update.publish_date, str):
                document.publish_date = datetime.strptime(
                    document_update.publish_date, "%Y-%m-%d"
                )
            else:
                document.publish_date = document_update.publish_date
        if document_update.corpus_id is not None:
            document.corpus_id = document_update.corpus_id

        # Si de nouveaux chunks sont fournis, les ajouter
        chunks_added = 0
        if new_chunks:
            # Préparer l'embedding generator
            eg = EmbeddingGenerator()
            bulk_rows = []

            # Générer des embeddings pour les nouveaux chunks
            for c in new_chunks:
                emb = eg.generate_embedding(c["content"])
                chunk_data = {
                    "document_id": document.id,
                    "content": c["content"],
                    "embedding": emb,
                    "start_char": c.get("start_char", 0),
                    "end_char": c.get("end_char", len(c["content"])),
                    "hierarchy_level": c.get("hierarchy_level", 3),
                    "parent_chunk_id": c.get("parent_chunk_id"),
                }
                bulk_rows.append(chunk_data)

            # Insérer tous les nouveaux chunks en une seule opération
            if bulk_rows:
                db.execute(insert(Chunk), bulk_rows)
                chunks_added = len(bulk_rows)

            # Mettre à jour le nombre de chunks dans la configuration d'index
            if chunks_added > 0:
                cfg = (
                    db.query(IndexConfig)
                    .filter(IndexConfig.corpus_id == document.corpus_id)
                    .first()
                )
                if cfg:
                    cfg.chunk_count += chunks_added

                    # Vérifier si un changement d'index est recommandé
                    if cfg.chunk_count > 300_000 and cfg.index_type == "ivfflat":
                        logger.warning(
                            "Corpus %s contient désormais %s chunks, envisager la migration vers un index HNSW",
                            document.corpus_id,
                            cfg.chunk_count,
                        )
                else:
                    # Créer une nouvelle configuration si elle n'existe pas
                    db.add(
                        IndexConfig(
                            corpus_id=document.corpus_id,
                            index_type="ivfflat",
                            chunk_count=chunks_added,
                        )
                    )

        # Vérifier si le corpus_id a changé, ce qui nécessite une mise à jour des index
        index_update_needed = False
        if old_corpus_id != document.corpus_id:
            # Mettre à jour les statistiques des deux corpus
            old_cfg = (
                db.query(IndexConfig)
                .filter(IndexConfig.corpus_id == old_corpus_id)
                .first()
            )
            new_cfg = (
                db.query(IndexConfig)
                .filter(IndexConfig.corpus_id == document.corpus_id)
                .first()
            )

            # Compter les chunks du document
            chunk_count = (
                db.query(Chunk).filter(Chunk.document_id == document.id).count()
            )

            if old_cfg:
                old_cfg.chunk_count = max(0, old_cfg.chunk_count - chunk_count)

            if new_cfg:
                new_cfg.chunk_count += chunk_count
            else:
                # Créer une configuration pour le nouveau corpus
                db.add(
                    IndexConfig(
                        corpus_id=document.corpus_id,
                        index_type="ivfflat",
                        chunk_count=chunk_count,
                    )
                )

            index_update_needed = True

        # Valider les modifications
        db.commit()
        db.refresh(document)

        # Récupérer le nombre total de chunks pour ce document
        total_chunks = db.query(Chunk).filter(Chunk.document_id == document.id).count()

        # Construire le résultat
        result = {
            "id": document.id,
            "title": document.title,
            "theme": document.theme,
            "document_type": document.document_type,
            "publish_date": document.publish_date,
            "corpus_id": document.corpus_id,
            "chunks": {"total": total_chunks, "added": chunks_added},
            "index_update_needed": index_update_needed,
        }

        return result

    except Exception as e:
        db.rollback()
        logger.error(
            "Erreur lors de la mise à jour du document %s: %s",
            document_update.document_id,
            str(e),
        )
        return {"error": str(e)}


def delete_document_chunks(
    document_id: int, chunk_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Supprime des chunks spécifiques d'un document ou tous les chunks si aucun ID n'est spécifié.

    Args:
        document_id: ID du document.
        chunk_ids: Liste des IDs des chunks à supprimer (si None, supprime tous les chunks).

    Returns:
        Dict[str, Any]: Résultat de l'opération.
    """
    db = next(get_db())
    try:
        # Vérifier que le document existe
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"error": f"Document avec ID {document_id} introuvable."}

        # Récupérer la configuration d'index pour ce corpus
        cfg = (
            db.query(IndexConfig)
            .filter(IndexConfig.corpus_id == document.corpus_id)
            .first()
        )

        # Supprimer les chunks spécifiés ou tous les chunks
        if chunk_ids:
            # Vérifier que les chunks appartiennent bien au document
            chunks_to_delete = (
                db.query(Chunk)
                .filter(Chunk.document_id == document_id, Chunk.id.in_(chunk_ids))
                .all()
            )

            if not chunks_to_delete:
                return {"warning": "Aucun chunk correspondant trouvé pour ce document."}

            # Mettre à jour le compteur de chunks dans la configuration d'index
            if cfg:
                cfg.chunk_count -= len(chunks_to_delete)

            # Supprimer les chunks spécifiés
            for chunk in chunks_to_delete:
                db.delete(chunk)

            deleted_count = len(chunks_to_delete)
        else:
            # Compter les chunks pour la mise à jour de la configuration d'index
            chunk_count = (
                db.query(Chunk).filter(Chunk.document_id == document_id).count()
            )

            if cfg:
                cfg.chunk_count -= chunk_count

            # Supprimer tous les chunks du document
            deleted_count = (
                db.query(Chunk).filter(Chunk.document_id == document_id).delete()
            )

        db.commit()

        # Construire le résultat
        result = {
            "document_id": document_id,
            "chunks_deleted": deleted_count,
            "remaining_chunks": db.query(Chunk)
            .filter(Chunk.document_id == document_id)
            .count(),
        }

        return result

    except Exception as e:
        db.rollback()
        logger.error(
            "Erreur lors de la suppression des chunks du document %s: %s",
            document_id,
            str(e),
        )
        return {"error": str(e)}


def delete_document(document_id: int) -> Dict[str, Any]:
    """Supprime un document de la base de données avec tous ses chunks associés.

    Args:
        document_id: ID du document à supprimer.

    Returns:
        Dict[str, Any]: Résultat de l'opération.
    """
    db = next(get_db())
    try:
        # Trouver le document à supprimer
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"error": f"Document avec ID {document_id} introuvable."}

        # Récupérer le corpus_id et mettre à jour la configuration d'index
        corpus_id = document.corpus_id
        if corpus_id:
            # Compter les chunks du document pour mettre à jour les compteurs
            chunk_count = (
                db.query(Chunk).filter(Chunk.document_id == document_id).count()
            )

            # Mettre à jour la configuration d'index
            cfg = (
                db.query(IndexConfig).filter(IndexConfig.corpus_id == corpus_id).first()
            )
            if cfg:
                cfg.chunk_count -= chunk_count

        # Supprimer le document (et ses chunks grâce à la cascade)
        db.delete(document)
        db.commit()

        logger.info("Document avec ID %s supprimé avec succès.", document_id)
        return {"success": f"Document avec ID {document_id} supprimé avec succès."}

    except Exception as e:
        db.rollback()
        logger.error(
            "Erreur lors de la suppression du document %s: %s", document_id, str(e)
        )
        return {"error": str(e)}


def check_and_update_indexes() -> Dict[str, Any]:
    """Vérifie et met à jour les index vectoriels selon les besoins.

    Cette fonction analyse les corpus et détermine si des index doivent être créés
    ou mis à jour en fonction du nombre de chunks.

    Returns:
        Dict[str, Any]: Résultat de l'opération avec les index créés/mis à jour.
    """
    db = next(get_db())
    try:
        results = {"indexes_created": 0, "indexes_updated": 0, "details": []}

        # Trouver les configurations d'index sans index créé
        configs_without_index = (
            db.query(IndexConfig).filter(IndexConfig.is_indexed == False).all()
        )

        for cfg in configs_without_index:
            # Créer l'index approprié pour ce corpus
            result = create_index_for_corpus(cfg.corpus_id, cfg.index_type)

            if "success" in result:
                results["indexes_created"] += 1
                results["details"].append(
                    {
                        "corpus_id": cfg.corpus_id,
                        "action": "create",
                        "index_type": cfg.index_type,
                        "result": "success",
                    }
                )
            else:
                results["details"].append(
                    {
                        "corpus_id": cfg.corpus_id,
                        "action": "create",
                        "index_type": cfg.index_type,
                        "result": "failed",
                        "error": result.get("error"),
                    }
                )

        # Vérifier les corpus avec beaucoup de chunks utilisant IVFFLAT
        large_ivfflat_corpora = (
            db.query(IndexConfig)
            .filter(
                IndexConfig.is_indexed == True,
                IndexConfig.index_type == "ivfflat",
                IndexConfig.chunk_count > 300_000,
            )
            .all()
        )

        for cfg in large_ivfflat_corpora:
            # Suggérer un changement d'index
            results["details"].append(
                {
                    "corpus_id": cfg.corpus_id,
                    "action": "recommend_switch_to_hnsw",
                    "current_chunks": cfg.chunk_count,
                    "message": f"Le corpus {cfg.corpus_id} contient {cfg.chunk_count} chunks. Envisagez de migrer vers HNSW.",
                }
            )

        return results

    except Exception as e:
        logger.error("Erreur lors de la vérification des index: %s", str(e))
        return {"error": str(e)}
