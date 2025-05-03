"""
Module de gestion des index vectoriels en arrière-plan.

Ce module fournit un worker qui peut être exécuté séparément pour
créer et maintenir les index pgvector sans bloquer les requêtes API.
"""

import time
import logging
import threading
import schedule
from typing import Dict, Any

from .database import (
    get_db,
    IndexConfig,
    create_index_for_corpus,
    synchronize_index_flags,
)

logger = logging.getLogger(__name__)


class IndexWorker:
    """Worker d'indexation qui s'exécute en arrière-plan pour créer et maintenir les index vectoriels.

    Attributes:
        running: Indique si le worker est actif.
        interval_minutes: Intervalle entre les vérifications d'index en minutes.
        thread: Thread du worker.
    """

    def __init__(self, interval_minutes: int = 5):
        """Initialise le worker d'indexation.

        Args:
            interval_minutes: Intervalle en minutes entre les vérifications d'index.
        """
        self.running = False
        self.interval_minutes = interval_minutes
        self.thread = None

    def start(self) -> None:
        """Démarre le worker d'indexation dans un thread séparé."""
        if self.thread is not None and self.thread.is_alive():
            logger.warning("Le worker d'indexation est déjà en cours d'exécution")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        logger.info(
            "Worker d'indexation démarré avec un intervalle de %d minutes",
            self.interval_minutes,
        )

    def stop(self) -> None:
        """Arrête le worker d'indexation."""
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=10)
        logger.info("Worker d'indexation arrêté")

    def _run(self) -> None:
        """Boucle principale du worker."""
        # Planifier la tâche d'indexation
        schedule.every(self.interval_minutes).minutes.do(self.process_pending_indexes)

        # Exécuter immédiatement une première fois
        self.process_pending_indexes()

        # Boucle principale
        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def process_pending_indexes(self) -> Dict[str, Any]:
        """Traite tous les index en attente.

        Returns:
            Dict[str, Any]: Résultat de l'opération d'indexation.
        """
        logger.info("Vérification des index en attente...")
        db = next(get_db())
        try:
            # 1. Synchroniser les drapeaux d'index
            synchronize_index_flags(db)

            # 2. Récupérer les corpus à indexer
            configs_to_index = (
                db.query(IndexConfig).filter(~IndexConfig.is_indexed).all()
            )

            results = {"indexed_count": 0, "failed_count": 0, "details": []}

            # 3. Indexer chaque corpus
            for cfg in configs_to_index:
                logger.info(f"Création d'index pour le corpus {cfg.corpus_id}")
                result = create_index_for_corpus(cfg.corpus_id, cfg.index_type)

                if "success" in result:
                    results["indexed_count"] += 1
                    results["details"].append(
                        {
                            "corpus_id": cfg.corpus_id,
                            "status": "success",
                            "index_type": cfg.index_type,
                        }
                    )
                else:
                    results["failed_count"] += 1
                    results["details"].append(
                        {
                            "corpus_id": cfg.corpus_id,
                            "status": "failed",
                            "index_type": cfg.index_type,
                            "error": result.get("error"),
                        }
                    )

            return results

        except Exception as e:
            logger.error(f"Erreur lors du traitement des index en attente: {e}")
            return {"error": str(e)}
        finally:
            db.close()


# Instance singleton du worker
index_worker = IndexWorker()


def start_background_indexer():
    """Démarre le worker d'indexation en arrière-plan."""
    index_worker.start()
