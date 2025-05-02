"""
schemas.py – Pydantic Data-Transfer Objects (DTO) used by the REST API.

    Aucune dépendance à SQLAlchemy ici : les modèles ORM restent dans
    database.py.  Chaque modèle décrit uniquement la *forme* des données
    transitant par l’API (corps de requête ou de réponse).
"""

from __future__ import annotations

from datetime import date
from typing import Any, List, Optional, Dict

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────────────────
# Helpers & global Config
# ──────────────────────────────────────────────────────────────
def _to_camel(s: str) -> str:
    head, *tail = s.split("_")
    return head + "".join(word.capitalize() for word in tail)


CamelConfig: ConfigDict = {
    "alias_generator": _to_camel,
    "populate_by_name": True,  # accepte les deux formes en entrée
}


# ──────────────────────────────────────────────────────────────
#     Documents  &  Chunks  –  CRUD
# ──────────────────────────────────────────────────────────────
class DocumentCreate(BaseModel):
    """Corps minimal pour créer un document (hors contenu)."""

    title: str
    theme: str
    document_type: str
    publish_date: date
    corpus_id: Optional[str] = None

    model_config = CamelConfig


class ChunkCreate(BaseModel):
    """Corps pour créer un chunk (texte + méta hiérarchiques)."""

    id: Optional[int] = None
    content: str
    start_char: int = Field(0, ge=0)
    end_char: int
    hierarchy_level: int = Field(3, ge=0, le=3)
    parent_chunk_id: Optional[int] = None

    model_config = CamelConfig


class DocumentWithChunks(BaseModel):
    """Payload complet pour `POST /database/documents`."""

    document: DocumentCreate
    chunks: List[ChunkCreate]

    model_config = CamelConfig

    def to_dict(self) -> dict:
        """Convertit le payload en dictionnaire où `document` et `chunks` sont convertis en dictionnaires.

        Returns:
            dict: Dictionnaire contenant le document et les chunks convertis.
        """
        return {
            "document": self.document.model_dump(),
            "chunks": [chunk.model_dump() for chunk in self.chunks],
        }


class DocumentResponse(BaseModel):
    """Réponse standard lorsqu’un document est renvoyé côté API.

    Attributs:
        id (int): Identifiant du document.
        title (str): Titre du document.
        theme (str): Thème du document.
        document_type (str): Type de document.
        publish_date (date): Date de publication.
        corpus_id (Optional[str]): Identifiant du corpus.
        chunk_count (int): Nombre de chunks associés (>= 0).
    """

    id: int
    title: str
    theme: str
    document_type: str
    publish_date: date
    corpus_id: Optional[str] = None
    chunk_count: int = Field(..., ge=0)

    model_config = CamelConfig


class DocumentUpdate(BaseModel):
    """Corps de mise à jour d'un document."""

    id: int
    title: Optional[str] = None
    theme: Optional[str] = None
    document_type: Optional[str] = Field(None, alias="documentType")
    publish_date: Optional[date] = Field(None, alias="publishDate")
    corpus_id: Optional[str] = Field(None, alias="corpusId")

    model_config = CamelConfig


class UpdateWithChunks(BaseModel):
    """
    Payload de mise-à-jour :

    * `document`  → DTO `DocumentUpdate`
    * `newChunks` → éventuelle liste de nouveaux chunks à ajouter
    """

    document: DocumentUpdate
    new_chunks: Optional[List[ChunkCreate]] = None  # ← valeur par défaut

    model_config = CamelConfig  # alias camelCase ⟺ JSON

    # utilitaire facultatif
    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.document.model_dump(),
            "new_chunks": (
                [c.model_dump() for c in self.new_chunks] if self.new_chunks else None
            ),
        }


# ──────────────────────────────────────────────────────────────
#     Search  –  request & response
# ──────────────────────────────────────────────────────────────
class HierarchicalContext(BaseModel):
    """Parents (level 0 – 2) d’un chunk lorsque `hierarchical=True`."""

    level_0: Optional[Dict[str, Any]] = None
    level_1: Optional[Dict[str, Any]] = None
    level_2: Optional[Dict[str, Any]] = None

    model_config = CamelConfig


class ChunkResult(BaseModel):
    """Un chunk classé dans la réponse de recherche."""

    chunk_id: int
    document_id: int
    title: str
    content: str
    theme: str
    document_type: str
    publish_date: date
    score: float
    hierarchy_level: int
    context: Optional[HierarchicalContext] = None

    model_config = CamelConfig


class SearchRequest(BaseModel):
    """Paramètres acceptés par `POST /search/hybrid_search`."""

    query: str
    top_k: int = Field(10, ge=1, alias="topK")
    theme: Optional[str] = None
    document_type: Optional[str] = Field(None, alias="documentType")
    start_date: Optional[date] = Field(None, alias="startDate")
    end_date: Optional[date] = Field(None, alias="endDate")
    corpus_id: Optional[str] = Field(None, alias="corpusId")
    hierarchical: bool = False
    hierarchy_level: Optional[int] = Field(None, alias="hierarchyLevel")

    model_config = CamelConfig


class SearchResponse(BaseModel):
    """Réponse complète du moteur de recherche."""

    query: str
    top_k: int = Field(..., alias="topK")
    total_results: int = Field(..., alias="totalResults")
    results: List[ChunkResult]

    model_config = CamelConfig
