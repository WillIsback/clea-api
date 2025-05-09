"""
schemas.py – Pydantic Data-Transfer Objects (DTO) used by the REST API.

    Aucune dépendance à SQLAlchemy ici : les modèles ORM restent dans
    database.py.  Chaque modèle décrit uniquement la *forme* des données
    transitant par l’API (corps de requête ou de réponse).
"""

from __future__ import annotations

from datetime import date, datetime
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
    index_needed: bool = False

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
    """Paramètres pour la recherche hybride.

    Combine la requête textuelle avec des filtres de métadonnées optionnels.
    """

    query: str = Field(..., description="Requête en langage naturel")
    top_k: int = Field(10, description="Nombre de résultats à retourner")
    theme: Optional[str] = Field(None, description="Filtre par thème")
    document_type: Optional[str] = Field(
        None, description="Filtre par type de document"
    )
    start_date: Optional[datetime] = Field(None, description="Date de début")
    end_date: Optional[datetime] = Field(None, description="Date de fin")
    corpus_id: Optional[int] = Field(None, description="ID du corpus")
    hierarchy_level: Optional[int] = Field(
        None, description="Niveau hiérarchique (0-2)"
    )
    hierarchical: bool = Field(False, description="Récupérer le contexte hiérarchique")
    filter_by_relevance: bool = Field(
        False, description="Filtrer les résultats sous le seuil de pertinence"
    )
    normalize_scores: bool = Field(
        False, description="Normaliser les scores entre 0 et 1"
    )
    
    model_config = CamelConfig


class SearchResponse(BaseModel):
    """Réponse à une requête de recherche.

    Contient les résultats triés par pertinence avec métadonnées et évaluation de confiance.
    """

    query: str = Field(..., description="Requête originale")
    topK: int = Field(..., description="Nombre de résultats demandés")
    totalResults: int = Field(..., description="Nombre total de résultats trouvés")
    results: List[ChunkResult] = Field(..., description="Résultats de la recherche")
    confidence: Optional[ConfidenceMetrics] = Field(
        None, description="Métriques de confiance sur les résultats"
    )
    normalized: bool = Field(
        False, description="Indique si les scores sont normalisés (0-1)"
    )
    message: Optional[str] = Field(
        None, description="Message informatif sur les résultats"
    )
    
    model_config = CamelConfig

class IndexStatus(BaseModel):
    """Statut de l'indexation d'un document."""

    corpus_id: Optional[str]
    index_exists: bool
    config_exists: bool
    is_indexed: bool
    index_type: Optional[str]
    chunk_count: int
    indexed_chunks: int
    last_indexed: Optional[date]

    model_config = CamelConfig


class ConfidenceMetrics(BaseModel):
    """Métriques de confiance pour les résultats de recherche.

    Fournit des informations sur la pertinence des résultats et des statistiques
    pour aider l'utilisateur à évaluer la qualité des réponses.
    """

    level: float = Field(..., description="Niveau de confiance entre 0 et 1")
    message: str = Field(..., description="Message explicatif sur la pertinence")
    stats: Dict[str, float] = Field(
        ..., description="Statistiques des scores (min, max, avg, median)"
    )
    
    model_config = CamelConfig
    
    
    
