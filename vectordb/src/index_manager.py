"""
Module de gestion des index vectoriels pour pgvector.

Ce module fournit des fonctions simples pour créer et gérer
des index vectoriels sur les chunks de documents.
"""

import logging
from datetime import datetime
from sqlalchemy import text, select

from .database import get_db, Document, Chunk, IndexConfig

# Configuration du logger
logger = logging.getLogger(__name__)


def create_simple_index(corpus_id: str) -> dict:
    """Crée un index vectoriel simple pour un corpus donné.

    Cette fonction crée un index IVFFLAT standard pour accélérer
    les recherches vectorielles sur un corpus spécifique.

    Args:
        corpus_id: Identifiant UUID du corpus à indexer.

    Returns:
        dict: Résultat de l'opération avec statut et message.
    """
    db = next(get_db())
    safe_corpus_id = corpus_id.replace("-", "_")
    index_name = f"idx_vector_{safe_corpus_id}"

    try:
        logger.info(f"Création d'un index vectoriel simple pour le corpus {corpus_id}")

        # 1. Vérifier si l'index existe déjà
        index_exists = (
            db.execute(
                text("SELECT 1 FROM pg_indexes WHERE indexname = :idx_name"),
                {"idx_name": index_name},
            ).fetchone()
            is not None
        )

        if index_exists:
            logger.info(f"L'index {index_name} existe déjà")

            # S'assurer que les documents sont marqués correctement même si l'index existe déjà
            db.query(Document).filter(Document.corpus_id == corpus_id).update(
                {Document.index_needed: False}
            )
            db.commit()

            return {"status": "exists", "message": f"L'index {index_name} existe déjà"}

        # 2. Compter les chunks pour ce corpus
        chunk_count = (
            db.query(Chunk)
            .join(Document)
            .filter(Document.corpus_id == corpus_id)
            .count()
        )

        if chunk_count == 0:
            return {
                "status": "error",
                "message": f"Aucun chunk trouvé pour le corpus {corpus_id}",
            }

        # 3. Créer une vue matérialisée temporaire contenant les chunks du corpus
        # Cette approche évite la sous-requête dans la clause WHERE
        view_name = f"temp_corpus_chunks_{safe_corpus_id}"

        # 3.1. Supprimer la vue si elle existe déjà
        db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))

        # 3.2. Créer une vue matérialisée avec les chunks du corpus
        create_view_sql = f"""
        CREATE MATERIALIZED VIEW {view_name} AS
        SELECT c.id, c.embedding
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.corpus_id = :corpus_id;
        """

        db.execute(text(create_view_sql), {"corpus_id": corpus_id})

        # 3.3. Nombre de listes optimal: environ racine carrée du nombre de vecteurs
        lists = min(max(int(chunk_count**0.5), 10), 1000)

        # 3.4. Créer l'index sur la vue matérialisée
        index_sql = f"""
        CREATE INDEX {index_name}
        ON {view_name} USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = {lists});
        """

        db.execute(text(index_sql))

        # 4. Mettre à jour la configuration d'index
        config = (
            db.query(IndexConfig).filter(IndexConfig.corpus_id == corpus_id).first()
        )
        if config:
            config.is_indexed = True
            config.index_type = "ivfflat"
            config.last_indexed = datetime.now()
            config.chunk_count = chunk_count
            config.ivf_lists = lists
        else:
            config = IndexConfig(
                corpus_id=corpus_id,
                index_type="ivfflat",
                is_indexed=True,
                chunk_count=chunk_count,
                last_indexed=datetime.now(),
                ivf_lists=lists,
            )
            db.add(config)

        # 5. Mettre à jour le drapeau index_needed des documents
        update_count = (
            db.query(Document)
            .filter(Document.corpus_id == corpus_id)
            .update(
                {Document.index_needed: False},
                synchronize_session=False,
            )
        )

        db.commit()
        logger.info(f"Mise à jour de {update_count} documents pour index_needed=False")

        # 6. Optimiser les statistiques dans une nouvelle transaction
        try:
            with next(get_db()) as analyze_db:
                analyze_db.execute(text(f"ANALYZE {view_name};"))
                analyze_db.execute(text("ANALYZE chunks; ANALYZE documents;"))
        except Exception as e:
            logger.warning(f"Impossible de mettre à jour les statistiques: {e}")

        return {
            "status": "success",
            "message": f"Index vectoriel créé pour {chunk_count} chunks dans le corpus {corpus_id}",
            "index_type": "ivfflat",
            "lists": lists,
            "documents_updated": update_count,
            "view_name": view_name,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la création de l'index: {e}")
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
