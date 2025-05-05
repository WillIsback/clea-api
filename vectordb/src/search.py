"""search.py – Recherche hybride sémantique et par métadonnées.

Framework de recherche documentaire hybride pour PostgreSQL + pgvector
"""

from __future__ import annotations
from typing import Any, Optional, List, Tuple, Dict
import statistics
from sqlalchemy import text
from sqlalchemy.orm import Session
from utils import get_logger

from .database import Chunk
from .embeddings import EmbeddingGenerator
from .ranking import ResultRanker

from .schemas import (
    SearchRequest,
    SearchResponse,
    ChunkResult,
    HierarchicalContext,
    ConfidenceMetrics,
)

# Configuration du logger
logger = get_logger("clea-api.vectordb.search")


# ─────────────────────────────────────────────────────────────── #
# Moteur de recherche                                            #
# ─────────────────────────────────────────────────────────────── #
class SearchEngine:
    """Moteur de recherche hybride (métadonnées + vecteur) avec rerank optionnel via Cross-Encoder.

    Utilise à la fois une recherche par similarité vectorielle et un rerank avec un modèle Cross-Encoder.
    Inclut une évaluation de la pertinence des résultats et détection des requêtes hors domaine.
    """

    def __init__(
        self,
        min_relevance_threshold: float = -0.0,
        high_confidence_threshold: float = 0.0,
    ) -> None:
        """Initialise le moteur de recherche avec son générateur d'embeddings et son ranker.

        Args:
            min_relevance_threshold: Score minimal pour qu'un résultat soit considéré pertinent.
            high_confidence_threshold: Score minimal pour une confiance élevée.
        """
        self._embedder = EmbeddingGenerator()
        self._ranker = ResultRanker()
        self.min_relevance_threshold = min_relevance_threshold
        self.high_confidence_threshold = high_confidence_threshold
        logger.debug(
            f"SearchEngine initialisé avec seuils: min_relevance={min_relevance_threshold}, "
            f"high_confidence={high_confidence_threshold}"
        )

    def evaluate_confidence(self, scores: List[float]) -> ConfidenceMetrics:
        """Évalue la confiance globale dans les résultats de recherche.

        Analyse les scores du ranker pour déterminer la pertinence globale des résultats
        et détecter les requêtes potentiellement hors domaine.

        Args:
            scores: Liste des scores de pertinence.

        Returns:
            Métriques de confiance avec niveau, message explicatif et statistiques.
        """
        if not scores:
            return ConfidenceMetrics(
                level=0.0,
                message="Aucun résultat trouvé.",
                stats={"min": 0.0, "max": 0.0, "avg": 0.0, "median": 0.0},
            )

        # Calcul des statistiques
        max_score = max(scores)
        min_score = min(scores)
        avg_score = sum(scores) / len(scores)
        median_score = statistics.median(scores)

        stats = {
            "min": min_score,
            "max": max_score,
            "avg": avg_score,
            "median": median_score,
        }

        # Évaluation du niveau de confiance et du message
        if max_score < self.min_relevance_threshold:
            level = 0.1
            message = "Requête probablement hors du domaine de connaissances."
        elif avg_score < 0:
            level = 0.4
            message = "Pertinence moyenne: résultats disponibles mais peu spécifiques."
        elif max_score > self.high_confidence_threshold:
            level = 0.9
            message = "Haute pertinence: résultats fiables trouvés."
        else:
            level = 0.7
            message = "Bonne pertinence: résultats généralement pertinents."

        logger.debug(
            f"Évaluation de confiance - niveau: {level}, max_score: {max_score}, avg: {avg_score}"
        )
        return ConfidenceMetrics(level=level, message=message, stats=stats)

    def normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalise les scores en valeurs entre 0 et 1.

        Args:
            scores: Liste des scores bruts du modèle.

        Returns:
            Liste de scores normalisés entre 0 et 1.
        """
        if not scores:
            return []
        threshold = self.min_relevance_threshold
        mn, mx = min(scores), max(scores)
        if mx <= threshold:
            # tous en dessous du seuil → non pertinents
            return [0.0] * len(scores)
        delta = mx - mn
        if delta == 0:
            # tous égaux mais > threshold → pertinence max
            return [1.0] * len(scores)
        return [(s - mn) / delta for s in scores]

    def hybrid_search(self, db: Session, req: SearchRequest) -> SearchResponse:
        """Exécute une recherche hybride avec évaluation de confiance.

        Combine recherche vectorielle et filtrage SQL, puis applique un reranking
        avec un modèle Cross-Encoder et évalue la pertinence des résultats.

        Args:
            db: Session SQLAlchemy.
            req: Paramètres de la recherche.

        Returns:
            Réponse formatée avec résultats triés, métriques de confiance et statistiques.
        """
        # Génération de l'embedding pour la requête
        logger.debug(f"Recherche hybride: '{req.query}', top_k={req.top_k}")
        q_emb = self._embedder.generate_embedding(req.query)

        # Construction et exécution de la requête SQL
        sql, params = self._build_sql(req)
        params.update(
            query_embedding=q_emb,
            expanded_limit=req.top_k * 3,  # Récupérer plus pour le reranking
            top_k=req.top_k,
        )

        raw_rows = db.execute(text(sql), params).fetchall()
        if not raw_rows:
            logger.info(f"Aucun résultat trouvé pour '{req.query}'")
            return SearchResponse(
                query=req.query,
                topK=req.top_k,
                totalResults=0,
                results=[],
                confidence=ConfidenceMetrics(
                    level=0.0,
                    message="Aucun résultat correspondant à votre recherche.",
                    stats={"min": 0, "max": 0, "avg": 0, "median": 0},
                ),
                normalized=True,
                message="Aucun résultat trouvé.",
            )

        # Rerank avec Cross-Encoder
        contents = [r.chunk_content for r in raw_rows]
        scores = self._ranker.rank_results(req.query, contents)

        # Évaluation de la confiance dans les résultats
        confidence = self.evaluate_confidence(scores)

        # Filtrer les résultats sous le seuil de pertinence si demandé
        if req.filter_by_relevance:
            filtered_results = [
                (row, score)
                for row, score in zip(raw_rows, scores)
                if score >= self.min_relevance_threshold
            ]

            if filtered_results:
                ranked = sorted(
                    filtered_results,
                    key=lambda t: t[1],
                    reverse=True,
                )[: req.top_k]
            else:
                logger.info(
                    f"Tous les résultats filtrés pour '{req.query}' (scores trop bas)"
                )
                return SearchResponse(
                    query=req.query,
                    topK=req.top_k,
                    totalResults=len(raw_rows),
                    results=[],
                    confidence=confidence,
                    normalized=False,
                    message="Résultats disponibles mais de faible pertinence.",
                )
        else:
            # Sans filtrage, trier simplement par score
            ranked = sorted(
                zip(raw_rows, scores),
                key=lambda t: t[1],
                reverse=True,
            )[: req.top_k]

        # Normalisation des scores si demandée
        if req.normalize_scores:
            ranked_scores = [s for _, s in ranked]
            normalized = self.normalize_scores(ranked_scores)

        # Création de la liste des résultats
        results: List[ChunkResult] = []
        for idx, (row, score) in enumerate(ranked):
            context = self._get_context(db, row.chunk_id) if req.hierarchical else None

            # Utiliser le score normalisé si demandé
            final_score = normalized[idx] if req.normalize_scores else score

            results.append(
                ChunkResult(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    title=row.document_title,
                    content=row.chunk_content,
                    theme=row.theme,
                    document_type=row.document_type,
                    publish_date=row.publish_date,
                    score=final_score,
                    hierarchy_level=row.hierarchy_level,
                    context=context,
                )
            )

        logger.info(
            f"Recherche '{req.query}': {len(results)} résultats, "
            f"confiance={confidence.level:.2f}, {confidence.message}"
        )

        return SearchResponse(
            query=req.query,
            topK=req.top_k,
            totalResults=len(raw_rows),
            results=results,
            confidence=confidence,
            normalized=req.normalize_scores,
            message=confidence.message,
        )

    @staticmethod
    def _build_sql(req: SearchRequest) -> Tuple[str, Dict[str, Any]]:
        """Assemble la requête SQL paramétrée et les paramètres associés.

        Args:
            req: Paramètres de la recherche.

        Returns:
            Tuple contenant la chaîne SQL et le dictionnaire des paramètres.
        """
        sql = """
        WITH ranked AS (
            SELECT
                c.id            AS chunk_id,
                c.content       AS chunk_content,
                c.hierarchy_level,
                c.parent_chunk_id,
                d.id            AS document_id,
                d.title         AS document_title,
                d.theme,
                d.document_type,
                d.publish_date,
                d.corpus_id,
                c.embedding <=> (:query_embedding)::vector AS distance
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE 1 = 1
        """
        p: Dict[str, Any] = {}

        if req.theme:
            sql += " AND d.theme = :theme"
            p["theme"] = req.theme
        if req.document_type:
            sql += " AND d.document_type = :dtype"
            p["dtype"] = req.document_type
        if req.start_date and req.end_date:
            sql += " AND d.publish_date BETWEEN :sd AND :ed"
            p.update(sd=req.start_date, ed=req.end_date)
        if req.corpus_id:
            sql += " AND d.corpus_id = :cid"
            p["cid"] = req.corpus_id
        if req.hierarchy_level is not None:
            sql += " AND c.hierarchy_level = :hlevel"
            p["hlevel"] = req.hierarchy_level

        sql += """
            ORDER BY distance
            LIMIT :expanded_limit
        )
        SELECT * FROM ranked
        ORDER BY distance
        LIMIT :top_k;
        """
        return sql, p

    @staticmethod
    def _get_context(db: Session, chunk_id: int) -> Optional[HierarchicalContext]:
        """Récupère le contexte hiérarchique (chunks parents) pour un chunk donné.

        Args:
            db: Session SQLAlchemy.
            chunk_id: Identifiant du chunk.

        Returns:
            Contexte hiérarchique ou None si inexistant.
        """
        ctx: Dict[str, Any] = {}
        cur = db.get(Chunk, chunk_id)
        while cur and cur.parent_chunk_id:
            parent = db.get(Chunk, cur.parent_chunk_id)
            if not parent:
                break
            ctx[f"level_{parent.hierarchy_level}"] = {
                "id": parent.id,
                "content": parent.content,
                "hierarchy_level": parent.hierarchy_level,
            }
            cur = parent
        return HierarchicalContext(**ctx) if ctx else None
