import logging
import os

from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    text,
)

from sqlalchemy.orm import (
    declarative_base,
    mapped_column,
    relationship,
    sessionmaker,
)
# ---------------------------------------------------------------------------

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


# Modèle ORM pour les documents
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
            db.query(IndexConfig).filter(~IndexConfig.is_indexed).all()
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
                IndexConfig.is_indexed,
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
