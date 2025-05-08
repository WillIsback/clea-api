"""
Module de gestion des index vectoriels pour pgvector.

Ce module fournit des fonctions simples pour créer et gérer
des index vectoriels sur les chunks de documents.
"""

from datetime import datetime
from sqlalchemy import text

from .database import get_db, Document, Chunk, IndexConfig

from utils import get_logger

# --------------------------------------------------------------------------- #
#  Configuration du logger
# --------------------------------------------------------------------------- #
logger = get_logger("vectordb.index_manager")


def create_simple_index(corpus_id: str) -> dict:
    """Crée un index vectoriel simple pour un corpus donné en utilisant SQLAlchemy uniquement."""
    db = next(get_db())
    safe_corpus_id = corpus_id.replace("-", "_")
    index_name = f"idx_vector_{safe_corpus_id}"
    view_name = f"temp_corpus_chunks_{safe_corpus_id}"

    try:
        logger.info(f"Création de l'index vectoriel pour le corpus {corpus_id}")

        # 1. Vérifier l'existence de l'index
        exists = db.execute(
            text("SELECT 1 FROM pg_indexes WHERE indexname = :idx"),
            {"idx": index_name}
        ).fetchone() is not None
        if exists:
            logger.info(f"L'index {index_name} existe déjà")
            db.query(Document).filter(Document.corpus_id == corpus_id)\
                .update({Document.index_needed: False}, synchronize_session=False)
            db.commit()
            return {"status": "exists", "message": f"Index {index_name} déjà présent"}

        # 2. Compter les chunks
        count = db.query(Chunk)\
            .join(Document)\
            .filter(Document.corpus_id == corpus_id)\
            .count()
        if count == 0:
            return {"status": "error", "message": "Aucun chunk pour ce corpus"}

        # 3. (Re)créer la vue matérialisée sans bind params
        db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
        create_view = f"""
            CREATE MATERIALIZED VIEW {view_name} AS
            SELECT c.id, c.embedding
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.corpus_id = '{corpus_id}';
        """
        db.execute(text(create_view))

        # 4. Créer l'index ivfflat
        lists = min(max(int(count ** 0.5), 10), 1000)
        create_idx = f"""
            CREATE INDEX {index_name}
            ON {view_name} USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {lists});
        """
        db.execute(text(create_idx))

        # 5. Mettre à jour IndexConfig et documents
        cfg = db.query(IndexConfig).filter(IndexConfig.corpus_id == corpus_id).first()
        if not cfg:
            cfg = IndexConfig(
                corpus_id=corpus_id,
                index_type="ivfflat",
                is_indexed=True,
                chunk_count=count,
                last_indexed=datetime.now(),
                ivf_lists=lists,
            )
            db.add(cfg)
        else:
            cfg.is_indexed = True
            cfg.chunk_count = count
            cfg.ivf_lists = lists
            cfg.last_indexed = datetime.now()

        updated = db.query(Document)\
            .filter(Document.corpus_id == corpus_id)\
            .update({Document.index_needed: False}, synchronize_session=False)
        db.commit()
        logger.info(f"Mis à jour {updated} docs index_needed=False")

        # 6. Analyse des statistiques
        try:
            with next(get_db()) as analyze_db:
                analyze_db.execute(text(f"ANALYZE {view_name}"))
                analyze_db.execute(text("ANALYZE chunks; ANALYZE documents;"))
        except Exception as e:
            logger.warning(f"ANALYZE échoué: {e}")

        return {"status": "success", "message": f"Index créé ({count} vecteurs)",
                "lists": lists, "view": view_name}

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur création index: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        db.close()

def drop_index(corpus_id: str) -> dict:
    """Supprime l'index vectoriel pour un corpus.

    Args:
        corpus_id: Identifiant UUID du corpus.

    Returns:
        dict: Résultat de l'opération.
    """
    db = next(get_db())
    safe_corpus_id = corpus_id.replace("-", "_")
    index_name = f"idx_vector_{safe_corpus_id}"
    view_name = f"temp_corpus_chunks_{safe_corpus_id}"

    try:
        # Vérifier si l'index existe
        index_exists = (
            db.execute(
                text("SELECT 1 FROM pg_indexes WHERE indexname = :idx_name"),
                {"idx_name": index_name},
            ).fetchone()
            is not None
        )

        if not index_exists:
            return {
                "status": "warning",
                "message": f"L'index {index_name} n'existe pas",
            }

        # Supprimer la vue matérialisée (ce qui supprimera aussi l'index)
        db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))

        # Mettre à jour la configuration
        config = (
            db.query(IndexConfig).filter(IndexConfig.corpus_id == corpus_id).first()
        )
        if config:
            config.is_indexed = False

        db.commit()
        return {
            "status": "success",
            "message": f"Index {index_name} et vue {view_name} supprimés avec succès",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la suppression de l'index: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def check_index_status(corpus_id: str) -> dict:
    """Vérifie l'état de l'index pour un corpus.

    Args:
        corpus_id: Identifiant UUID du corpus.

    Returns:
        dict: État de l'index et métadonnées.
    """
    db = next(get_db())
    safe_corpus_id = corpus_id.replace("-", "_")
    index_name = f"idx_vector_{safe_corpus_id}"

    try:
        # Vérifier si l'index existe dans PostgreSQL
        index_exists = (
            db.execute(
                text("SELECT 1 FROM pg_indexes WHERE indexname = :idx_name"),
                {"idx_name": index_name},
            ).fetchone()
            is not None
        )

        # Récupérer la configuration d'index
        config = (
            db.query(IndexConfig).filter(IndexConfig.corpus_id == corpus_id).first()
        )

        # Compter les chunks pour ce corpus
        chunk_count = (
            db.query(Chunk)
            .join(Document)
            .filter(Document.corpus_id == corpus_id)
            .count()
        )

        return {
            "corpus_id": corpus_id,
            "index_exists": index_exists,
            "config_exists": config is not None,
            "is_indexed": config.is_indexed if config else False,
            "index_type": config.index_type if config else None,
            "chunk_count": chunk_count,
            "indexed_chunks": config.chunk_count if config else 0,
            "last_indexed": config.last_indexed if config else None,
        }

    except Exception as e:
        logger.error(f"Erreur lors de la vérification de l'index: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def check_all_indexes() -> dict:
    """Vérifie l'état de tous les index vectoriels.

    Returns:
        dict: État des index pour tous les corpus.
    """
    db = next(get_db())
    try:
        # Récupérer tous les corpus uniques
        corpus_ids = [r[0] for r in db.query(Document.corpus_id).distinct().all()]

        results = []
        for corpus_id in corpus_ids:
            if not corpus_id:
                continue
            status = check_index_status(corpus_id)
            results.append(status)

        return {"status": "success", "corpus_count": len(results), "indexes": results}

    except Exception as e:
        logger.error(f"Erreur lors de la vérification des index: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
