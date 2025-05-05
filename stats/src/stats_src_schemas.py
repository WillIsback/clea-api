
from pydantic import BaseModel, ConfigDict
from typing import Any, List, Dict


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
#     Documents  / Search / System –  Stats
# ──────────────────────────────────────────────────────────────

class DocumentStats(BaseModel):
    """Corps pour créer un chunk (texte + méta hiérarchiques)."""

    total_count: int
    by_theme: Dict[str, int]
    by_type: Dict[str, int]
    recently_added: int # 30 derniers jours
    percent_change: float # Evolution en pourcentage
    
    model_config = CamelConfig

class SearchStats(BaseModel):
    """Payload complet pour `POST /database/documents`."""

    total_count: int
    last_month_count: int
    percent_change: float # Evolution en pourcentage
    top_queries: List[Dict[str, Any]] # [{query: str, count: int}, ...] Requêtes les plus populaires
    
    model_config = CamelConfig

class SystemStats(BaseModel):
    """Payload complet pour `POST /database/documents`."""

    satisfaction: float # Note de satisfaction en pourcentage
    avg_confidence: float # Note de confiance moyenne en pourcentage
    percent_change: float # Evolution en pourcentage
    indexed_corpora: int # Nombre de documents indexés
    total_corpora: int # Nombre total de documents
    model_config = CamelConfig
    
    
class DashboardStats(BaseModel):
    """Corps minimal pour créer un document (hors contenu)."""

    document_stats: DocumentStats
    search_stats: SearchStats
    system_stats: SystemStats

    model_config = CamelConfig
