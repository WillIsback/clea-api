"""search.py – Hybrid semantic / metadata search.

Hybrid document-search framework for PostgreSQL + pgvector
"""

from __future__ import annotations
from typing import Any, Optional, List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import Chunk
from .embeddings import EmbeddingGenerator
from .ranking import ResultRanker

from .schemas import (
    SearchRequest,
    SearchResponse,
    ChunkResult,
    HierarchicalContext,
)


# ─────────────────────────────────────────────────────────────── #
# Moteur de recherche                                            #
# ─────────────────────────────────────────────────────────────── #
class SearchEngine:
    """Moteur de recherche hybride (métadonnées + vecteur) avec rerank optionnel via Cross-Encoder.

    Utilise à la fois une recherche par similarité vectorielle et un rerank avec un modèle Cross-Encoder.
    """

    def __init__(self) -> None:
        """Initialise le moteur de recherche avec son générateur d’embeddings et son ranker."""
        self._embedder = EmbeddingGenerator()
        self._ranker = ResultRanker()

    def hybrid_search(self, db: Session, req: SearchRequest) -> SearchResponse:
        """Exécute une recherche hybride et renvoie une réponse formatée selon le modèle SearchResponse.

        Args:
            db (Session): Session SQLAlchemy.
            req (SearchRequest): Paramètres de la recherche.

        Returns:
            SearchResponse: Réponse contenant la requête, le nombre de résultats demandés,
            le nombre total de résultats et une liste de chunks exposés en camelCase.
        """
        # Génération de l'embedding pour la requête
        q_emb = self._embedder.generate_embedding(req.query)

        sql, params = self._build_sql(req)
        params.update(
            query_embedding=q_emb,
            expanded_limit=req.top_k * 3,
            top_k=req.top_k,
        )

        raw_rows = db.execute(text(sql), params).fetchall()
        if not raw_rows:
            return SearchResponse(
                query=req.query,
                topK=req.top_k,
                totalResults=0,
                results=[],
            )

        # Rerank avec Cross-Encoder
        contents = [r.chunk_content for r in raw_rows]
        scores = self._ranker.rank_results(req.query, contents)

        ranked = sorted(
            zip(raw_rows, scores),
            key=lambda t: t[1],
            reverse=True,
        )[: req.top_k]

        # Création de la liste des résultats
        results: List[ChunkResult] = []
        for row, score in ranked:
            context = self._get_context(db, row.chunk_id) if req.hierarchical else None
            results.append(
                ChunkResult(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    title=row.document_title,
                    content=row.chunk_content,
                    theme=row.theme,
                    document_type=row.document_type,
                    publish_date=row.publish_date,
                    score=score,
                    hierarchy_level=row.hierarchy_level,
                    context=context,
                )
            )

        return SearchResponse(
            query=req.query,
            topK=req.top_k,
            totalResults=len(raw_rows),
            results=results,
        )

    @staticmethod
    def _build_sql(req: SearchRequest) -> Tuple[str, dict[str, Any]]:
        """Assemble la requête SQL paramétrée et les paramètres associés.

        Args:
            req (SearchRequest): Paramètres de la recherche.

        Returns:
            Tuple[str, dict[str, Any]]: Chaîne SQL et dictionnaire des paramètres.
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
        p: dict[str, Any] = {}

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
            db (Session): Session SQLAlchemy.
            chunk_id (int): Identifiant du chunk.

        Returns:
            Optional[HierarchicalContext]: Contexte hiérarchique ou None si inexistant.
        """
        ctx: dict[str, Any] = {}
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
