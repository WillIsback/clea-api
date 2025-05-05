import logging
import os

from datetime import datetime


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

from utils import get_logger
# ---------------------------------------------------------------------------

load_dotenv()

# Configuration de la base de données
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "vectordb")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# --------------------------------------------------------------------------- #
#  Configuration du logger
# --------------------------------------------------------------------------- #
logger = get_logger("vectordb.database")


# Création du moteur SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Document(Base):
    """Modèle SQLAlchemy pour la table des documents.

    Stocke les métadonnées globales des documents sans leur contenu.

    Attributes:
        id: Identifiant unique du document.
        title: Titre du document.
        theme: Thème ou catégorie du document.
        document_type: Type de document (PDF, DOCX, etc.).
        publish_date: Date de publication du document.
        corpus_id: UUID du corpus auquel appartient ce document.
        created_at: Date de création dans la base de données.
        index_needed: Indique si une mise à jour d'index est nécessaire pour ce document.
        chunks: Relation avec les fragments textuels du document.
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
    index_needed = mapped_column(Boolean, default=False)

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


##############################################################
#  Fonction helper
##############################################################
# def check_and_update_indexes() -> Dict[str, Any]:
#     """Vérifie et met à jour les index vectoriels selon les besoins.

#     Cette fonction analyse les corpus et détermine si des index doivent être créés
#     ou mis à jour en fonction du nombre de chunks.

#     Returns:
#         Dict[str, Any]: Résultat de l'opération avec les index créés/mis à jour.
#     """
#     db = next(get_db())
#     try:
#         results = {"indexes_created": 0, "indexes_updated": 0, "details": []}

#         # Trouver les configurations d'index sans index créé
#         configs_without_index = (
#             db.query(IndexConfig).filter(~IndexConfig.is_indexed).all()
#         )

#         for cfg in configs_without_index:
#             # Créer l'index approprié pour ce corpus
#             result = create_index_for_corpus(cfg.corpus_id, cfg.index_type)

#             if "success" in result:
#                 results["indexes_created"] += 1
#                 results["details"].append(
#                     {
#                         "corpus_id": cfg.corpus_id,
#                         "action": "create",
#                         "index_type": cfg.index_type,
#                         "result": "success",
#                     }
#                 )
#             else:
#                 results["details"].append(
#                     {
#                         "corpus_id": cfg.corpus_id,
#                         "action": "create",
#                         "index_type": cfg.index_type,
#                         "result": "failed",
#                         "error": result.get("error"),
#                     }
#                 )

#         # Vérifier les corpus avec beaucoup de chunks utilisant IVFFLAT
#         large_ivfflat_corpora = (
#             db.query(IndexConfig)
#             .filter(
#                 IndexConfig.is_indexed,
#                 IndexConfig.index_type == "ivfflat",
#                 IndexConfig.chunk_count > 300_000,
#             )
#             .all()
#         )

#         for cfg in large_ivfflat_corpora:
#             # Suggérer un changement d'index
#             results["details"].append(
#                 {
#                     "corpus_id": cfg.corpus_id,
#                     "action": "recommend_switch_to_hnsw",
#                     "current_chunks": cfg.chunk_count,
#                     "message": f"Le corpus {cfg.corpus_id} contient {cfg.chunk_count} chunks. Envisagez de migrer vers HNSW.",
#                 }
#             )

#         return results

#     except Exception as e:
#         logger.error("Erreur lors de la vérification des index: %s", str(e))
#         return {"error": str(e)}


# def synchronize_index_flags(db=None):
#     """Synchronise les drapeaux index_needed des documents avec l'état des index.

#     Parcourt tous les documents et met à jour leur champ index_needed en fonction
#     de l'état des configurations d'index de leur corpus.

#     Args:
#         db: Session de base de données. Si None, une nouvelle session sera créée.

#     Returns:
#         Dict[str, Any]: Statistiques sur la synchronisation effectuée.
#     """
#     close_db = False
#     if db is None:
#         db = next(get_db())
#         close_db = True

#     try:
#         # 1. Récupérer les corpus nécessitant un index
#         need_index_corpus_ids = [
#             row[0]
#             for row in db.query(IndexConfig.corpus_id)
#             .filter(
#                 ~IndexConfig.is_indexed
#             )  # Correction style: ~x au lieu de x == False
#             .all()
#         ]

#         # 2. Mettre à jour les documents de ces corpus qui n'ont pas encore le flag
#         updated = 0
#         if need_index_corpus_ids:
#             updated = (
#                 db.query(Document)
#                 .filter(
#                     Document.corpus_id.in_(need_index_corpus_ids),
#                     ~Document.index_needed,  # Correction style: ~x au lieu de x == False
#                 )
#                 .update({Document.index_needed: True}, synchronize_session=False)
#             )

#         # 3. Réinitialiser les documents dont les corpus sont déjà indexés
#         # Correction du problème de type - toujours utiliser une expression SQLAlchemy
#         reset_query = db.query(Document).filter(
#             Document.index_needed
#         )  # Style: x au lieu de x == True

#         # Si nous avons des corpus à indexer, ajouter la condition d'exclusion
#         if need_index_corpus_ids:
#             reset_query = reset_query.filter(
#                 ~Document.corpus_id.in_(need_index_corpus_ids)
#             )

#         # Exécuter la mise à jour
#         reset = reset_query.update(
#             {Document.index_needed: False}, synchronize_session=False
#         )

#         db.commit()

#         result = {
#             "updated_count": updated,
#             "reset_count": reset,
#             "total_affected": updated + reset,
#         }

#         return result

#     except Exception as e:
#         db.rollback()
#         logger.error(f"Erreur lors de la synchronisation des drapeaux d'index: {e}")
#         return {"error": str(e)}

#     finally:
#         if close_db:
#             db.close()


# def create_index_for_corpus(corpus_id, index_type="ivfflat", force=False):
#     """Crée un index vectoriel pour un corpus spécifique.

#     Cette fonction crée ou met à jour un index vectoriel pour les chunks d'un corpus
#     et met à jour les drapeaux index_needed des documents concernés.

#     Args:
#         corpus_id: Identifiant du corpus.
#         index_type: Type d'index ('ivfflat', 'hnsw' ou 'auto').
#         force: Si True, recréera l'index même s'il existe déjà.

#     Returns:
#         dict: Résultat de l'opération avec les informations sur l'index créé.
#     """
#     db = next(get_db())
#     try:
#         # Vérifier si le corpus existe déjà avec un index
#         config = (
#             db.query(IndexConfig).filter(IndexConfig.corpus_id == corpus_id).first()
#         )

#         # Compter le nombre de chunks dans ce corpus
#         chunk_count = (
#             db.query(Chunk)
#             .join(Document)
#             .filter(Document.corpus_id == corpus_id)
#             .count()
#         )

#         if chunk_count == 0:
#             return {"error": f"Aucun chunk trouvé pour le corpus {corpus_id}"}

#         # Si aucune configuration n'existe, en créer une nouvelle
#         if not config:
#             # Sélectionner automatiquement le type d'index en fonction du nombre de chunks
#             if index_type == "auto":
#                 index_type = "hnsw" if chunk_count > 300000 else "ivfflat"

#             config = IndexConfig(
#                 corpus_id=corpus_id, index_type=index_type, chunk_count=chunk_count
#             )
#             db.add(config)
#             db.flush()
#         else:
#             # Mise à jour du comptage de chunks
#             config.chunk_count = chunk_count

#             # Si déjà indexé et pas force=True, ne pas recréer
#             if config.is_indexed and not force:
#                 # Vérifier si l'index existe réellement dans PostgreSQL
#                 index_name = f"chunks_embedding_{config.index_type}_{corpus_id.replace('-', '_')}"
#                 index_exists = (
#                     db.execute(
#                         text("SELECT 1 FROM pg_indexes WHERE indexname = :idx_name"),
#                         {"idx_name": index_name},
#                     ).fetchone()
#                     is not None
#                 )

#                 if index_exists:
#                     return {
#                         "message": f"Le corpus {corpus_id} est déjà indexé (type: {config.index_type}). "
#                         f"Utilisez force=True pour recréer l'index.",
#                         "corpus_id": corpus_id,
#                         "index_type": config.index_type,
#                     }
#                 # Si l'index n'existe pas vraiment, on continue pour le recréer
#                 else:
#                     logger.warning(
#                         f"L'index {index_name} est marqué comme existant mais n'existe pas dans PostgreSQL. Recréation..."
#                     )
#                     config.is_indexed = False

#             # Mise à jour du type d'index si nécessaire
#             if index_type != "auto" and config.index_type != index_type:
#                 config.index_type = index_type
#                 config.is_indexed = False

#             # Supprimer l'ancien index si nécessaire
#             if config.is_indexed and (
#                 force or index_type != "auto" and config.index_type != index_type
#             ):
#                 try:
#                     current_index_name = f"chunks_embedding_{config.index_type}_{corpus_id.replace('-', '_')}"
#                     db.execute(text(f"DROP INDEX IF EXISTS {current_index_name}"))
#                     config.is_indexed = False
#                 except Exception as e:
#                     logger.error(
#                         f"Erreur lors de la suppression de l'ancien index: {e}"
#                     )

#         # Récupérer les IDs des chunks à indexer
#         chunk_ids = [
#             row[0]
#             for row in db.query(Chunk.id)
#             .join(Document)
#             .filter(Document.corpus_id == corpus_id)
#             .all()
#         ]

#         if not chunk_ids:
#             return {"error": f"Aucun chunk trouvé pour le corpus {corpus_id}"}

#         # Création de l'index avec une approche compatible
#         index_name = (
#             f"chunks_embedding_{config.index_type}_{corpus_id.replace('-', '_')}"
#         )

#         # Utilisons une table temporaire pour garantir la compatibilité avec la recherche
#         try:
#             # Créer une table temporaire contenant les IDs des chunks à indexer
#             db.execute(
#                 text(
#                     "CREATE TEMP TABLE IF NOT EXISTS tmp_chunk_ids (id INTEGER NOT NULL)"
#                 )
#             )
#             db.execute(text("TRUNCATE tmp_chunk_ids"))

#             # Insérer par lots de 1000 pour éviter les problèmes de mémoire
#             for i in range(0, len(chunk_ids), 1000):
#                 batch = chunk_ids[i : i + 1000]
#                 values = ", ".join(f"({id})" for id in batch)
#                 db.execute(text(f"INSERT INTO tmp_chunk_ids (id) VALUES {values}"))

#             # Créer l'index en utilisant la table temporaire
#             if config.index_type == "ivfflat":
#                 sql = f"""
#                 CREATE INDEX {index_name}
#                 ON chunks USING ivfflat (embedding vector_cosine_ops)
#                 WITH (lists = {config.ivf_lists})
#                 WHERE id IN (SELECT id FROM tmp_chunk_ids)
#                 """
#             else:  # hnsw
#                 sql = f"""
#                 CREATE INDEX {index_name}
#                 ON chunks USING hnsw (embedding vector_cosine_ops)
#                 WITH (m = {config.hnsw_m}, ef_construction = {config.hnsw_ef_construction})
#                 WHERE id IN (SELECT id FROM tmp_chunk_ids)
#                 """

#             db.execute(text(sql))

#             # Mettre à jour le statut d'indexation
#             config.is_indexed = True
#             config.last_indexed = datetime.now()

#             # Mettre à jour le drapeau index_needed des documents
#             db.query(Document).filter(Document.corpus_id == corpus_id).update(
#                 {Document.index_needed: False}, synchronize_session=False
#             )

#             db.commit()

#             # Créer une statistique pour améliorer les performances de recherche
#             try:
#                 db.execute(
#                     text("""
#                     ANALYZE chunks;
#                     ANALYZE documents;
#                 """)
#                 )
#             except Exception as stats_error:
#                 logger.warning(
#                     f"Impossible de mettre à jour les statistiques: {stats_error}"
#                 )

#             return {
#                 "success": f"Index {config.index_type} créé avec succès pour le corpus {corpus_id}",
#                 "corpus_id": corpus_id,
#                 "index_type": config.index_type,
#                 "chunk_count": chunk_count,
#             }

#         except Exception as e:
#             db.rollback()
#             logger.error(f"Échec de création de l'index: {e}")
#             return {"error": f"Échec de création de l'index: {str(e)}"}
#         finally:
#             # Nettoyage de la table temporaire
#             try:
#                 db.execute(text("DROP TABLE IF EXISTS tmp_chunk_ids"))
#             except Exception:
#                 pass

#     except Exception as e:
#         db.rollback()
#         logger.error(f"Erreur lors de la gestion de l'index: {e}")
#         return {"error": f"Erreur lors de la gestion de l'index: {str(e)}"}
#     finally:
#         db.close()
