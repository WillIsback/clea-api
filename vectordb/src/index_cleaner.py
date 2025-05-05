"""
Module de nettoyage des index vectoriels orphelins.

Ce module fournit des fonctions pour identifier et supprimer les index
vectoriels et configurations qui ne sont plus associés à des corpus existants.
"""

from __future__ import annotations
from typing import Dict, Any
from sqlalchemy import text
from datetime import datetime

from .database import get_db, Document, IndexConfig
from utils import get_logger

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Configuration du logger
logger = get_logger("vectordb.index_cleaner")


def clean_orphaned_indexes() -> Dict[str, Any]:
    """Nettoie les index vectoriels orphelins de la base de données.
    
    Cette fonction identifie et supprime les configurations d'index qui
    correspondent à des corpus qui n'existent plus dans la table documents.
    Elle supprime également les vues matérialisées et index associés dans PostgreSQL.
    
    Returns:
        Dict[str, Any]: Résultat de l'opération avec statistiques.
    """
    db = next(get_db())
    deleted_count = 0
    errors = []
    cleaned_corpus_ids = []
    
    try:
        # 1. Récupérer tous les corpus_ids existants dans les documents
        existing_corpus_ids = {
            corpus_id for (corpus_id,) in db.query(Document.corpus_id)
            .filter(Document.corpus_id.isnot(None))
            .distinct().all()
        }
        
        # 2. Récupérer toutes les configurations d'index
        index_configs = db.query(IndexConfig).all()
        
        # 3. Identifier les configurations orphelines
        for config in index_configs:
            if config.corpus_id not in existing_corpus_ids:
                try:
                    # Supprimer les ressources PostgreSQL associées (vue matérialisée, index)
                    safe_corpus_id = config.corpus_id.replace("-", "_")
                    view_name = f"temp_corpus_chunks_{safe_corpus_id}"
                    
                    # Vérifier si la vue existe avant de tenter de la supprimer
                    view_exists = db.execute(
                        text("SELECT 1 FROM pg_matviews WHERE matviewname = :view_name"),
                        {"view_name": view_name}
                    ).fetchone() is not None
                    
                    if view_exists:
                        logger.info(f"Suppression de la vue matérialisée orpheline: {view_name}")
                        db.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
                    
                    # Supprimer la configuration d'index
                    db.delete(config)
                    deleted_count += 1
                    cleaned_corpus_ids.append(config.corpus_id)
                    logger.info(f"Configuration d'index orpheline supprimée pour corpus_id: {config.corpus_id}")
                    
                except Exception as e:
                    error_msg = f"Erreur lors du nettoyage de l'index pour corpus_id {config.corpus_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
        
        # Valider les changements
        db.commit()
        
        # Optimiser les statistiques PostgreSQL
        if deleted_count > 0:
            try:
                db.execute(text("ANALYZE index_configs;"))
            except Exception as e:
                logger.warning(f"Impossible de mettre à jour les statistiques PostgreSQL: {str(e)}")
        
        return {
            "status": "success" if not errors else "partial_success",
            "deleted_count": deleted_count,
            "errors": errors,
            "cleaned_corpus_ids": cleaned_corpus_ids,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors du nettoyage des index orphelins: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
    finally:
        db.close()


def schedule_cleanup_job(interval_hours: int = 24) -> None:
    """Configure un job périodique pour nettoyer les index orphelins.
    
    Cette fonction peut être utilisée pour programmer un nettoyage automatique
    des index orphelins à intervalles réguliers.
    
    Args:
        interval_hours: Intervalle en heures entre deux nettoyages.
    """
    # Cette implémentation dépendra de votre système de tâches périodiques
    # Vous pourriez utiliser APScheduler, Celery, ou un simple thread avec time.sleep
    
    # Exemple avec APScheduler (nécessite l'installation du package)
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            clean_orphaned_indexes,
            IntervalTrigger(hours=interval_hours),
            id='index_cleanup_job',
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"Job de nettoyage des index programmé toutes les {interval_hours} heures")
    except ImportError:
        logger.warning("APScheduler n'est pas installé. Le nettoyage automatique n'est pas activé.")