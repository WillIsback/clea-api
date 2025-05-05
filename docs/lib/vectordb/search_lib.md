# Module **search** (Hybrid Semantic / Metadata Search)

Ce module implémente un moteur de recherche hybride combinant filtres SQL, similarité vectorielle (pgvector) et rerank via Cross-Encoder.

---

## Table des matières

1. [Installation](#installation)
2. [Modèles (schemas)](#modeles-schemas)
3. [Classe `SearchEngine`](#classe-searchengine)
   * [Constructeur](#constructeur)
   * [Méthode `hybrid_search`](#methode-hybrid_search) 
   * [Méthode `log_search_query`](#methode-log_search_query)
   * [Méthode `evaluate_confidence`](#methode-evaluate_confidence)
   * [Méthode `normalize_scores`](#methode-normalize_scores)
   * [Méthode privée `_build_sql`](#methode-privee-_build_sql)
   * [Méthode privée `_get_context`](#methode-privee-_get_context) 
4. [Historisation des recherches](#historisation-des-recherches)
5. [Exemple d'utilisation](#exemple-dutilisation)

---

## Installation

```bash
uv pip install clea_vectordb  # ou via votre setup.py/pyproject.toml
```

---

## Modèles (schemas)

Les Pydantic schemas utilisés par le moteur se trouvent dans `vectordb/src/schemas.py` :

* **`SearchRequest`** : paramètres de la recherche (requête, filtres, pagination, etc.).
* **`ChunkResult`** : un chunk renvoyé (camelCase).
* **`HierarchicalContext`** : contexte parent (niveaux 0–2).
* **`SearchResponse`** : enveloppe de réponse (requête, total, liste des `ChunkResult`).

> Pour la définition détaillée de ces schémas, référez-vous à la section **Components → Schemas** dans votre OpenAPI/Swagger.

---

## Classe `SearchEngine`&#x20;

### Constructeur

```python
engine = SearchEngine()
```

* **Initialise** :

  * un générateur d'embeddings (`EmbeddingGenerator`)
  * un ranker Cross-Encoder (`ResultRanker`)
  * les seuils de pertinence configurables (`min_relevance_threshold`, `high_confidence_threshold`)

<a id="methode-hybrid_search"></a>

### Méthode `hybrid_search`

```python
def hybrid_search(self, db: Session, req: SearchRequest) -> SearchResponse:
    ...
```

* **Arguments**

  * `db: Session` – session SQLAlchemy
  * `req: SearchRequest` – paramètres de la recherche

* **Fonctionnement**

  1. Génère l'embedding de la requête.
  2. Monte la requête SQL pour ANN + métadonnées (via `_build_sql`).
  3. Exécute `db.execute(text(sql), params)`.
  4. Si pas de résultat, renvoie un `SearchResponse` vide.
  5. Rerank les top *k × 3* résultats avec un Cross-Encoder.
  6. Construit la liste finale de `ChunkResult`, en récupérant le contexte hiérarchique si `req.hierarchical=True`.
  7. Historise la recherche dans la base de données via `log_search_query`.
  8. Renvoie un `SearchResponse(query, topK, totalResults, results)` .

* **Retour**

  * `SearchResponse` contenant :

    * `query` (str)
    * `topK` (int)
    * `totalResults` (int)
    * `results` (`List[ChunkResult]`)
    * `confidence` (`ConfidenceMetrics`)
    * `normalized` (bool)
    * `message` (str)

<a id="methode-log_search_query"></a>

### Méthode `log_search_query`

```python
def log_search_query(self, db: Session, req: SearchRequest, response: SearchResponse) -> None:
    ...
```

* **Arguments**
  * `db: Session` – session SQLAlchemy active
  * `req: SearchRequest` – requête de recherche soumise
  * `response: SearchResponse` – réponse générée avec les résultats

* **Fonctionnement**
  1. Crée une entrée dans la table `SearchQuery` avec les informations sur la recherche
  2. Persiste les métadonnées de la requête (texte, thème, type de document, corpus)
  3. Enregistre les métriques de résultats (nombre, niveau de confiance)
  4. Gère silencieusement les erreurs pour ne pas perturber le flux principal

<a id="methode-evaluate_confidence"></a>

### Méthode `evaluate_confidence`

```python
def evaluate_confidence(self, scores: List[float]) -> ConfidenceMetrics:
    ...
```

* **But** : analyser les scores des résultats pour déterminer la pertinence globale et détecter les requêtes hors domaine.
* **Arguments** : 
  * `scores: List[float]` – liste des scores de pertinence issus du ranker
* **Fonctionnement** :
  1. Calcule les statistiques de base (min, max, moyenne, médiane)
  2. Détermine le niveau de confiance (0.1 à 0.9) et le message associé
  3. Les seuils utilisés sont `min_relevance_threshold` et `high_confidence_threshold`
* **Niveaux de confiance** :
  * `0.1` – "Requête probablement hors du domaine de connaissances"
  * `0.4` – "Pertinence moyenne: résultats disponibles mais peu spécifiques"
  * `0.7` – "Bonne pertinence: résultats généralement pertinents"
  * `0.9` – "Haute pertinence: résultats fiables trouvés"
* **Retour** : `ConfidenceMetrics` contenant le niveau, le message et les statistiques

<a id="methode-normalize_scores"></a>

### Méthode `normalize_scores`

```python
def normalize_scores(self, scores: List[float]) -> List[float]:
    ...
```

* **But** : transformer les scores bruts (potentiellement négatifs) en valeurs entre 0 et 1
* **Arguments** : 
  * `scores: List[float]` – liste des scores bruts du modèle
* **Retour** : liste de scores normalisés entre 0 et 1, facilitant l'interprétation

<a id="methode-privee-_build_sql"></a>

### Méthode privée `_build_sql`

```python
@staticmethod
def _build_sql(req: SearchRequest) -> Tuple[str, dict[str, Any]]:
    ...
```

* **But** : assembler dynamiquement la clause `WHERE` SQL selon les filtres de `req`
* **Filtres gérés** :

  * `theme`, `document_type`
  * plage `start_date`–`end_date`
  * `corpus_id`
  * `hierarchy_level`
* **Structure** :

  ```sql
  WITH ranked AS (
    SELECT …, c.embedding <=> (:query_embedding)::vector AS distance
    FROM chunks c JOIN documents d ON …
    WHERE 1=1
      [AND d.theme = :theme]
      [AND …]
    ORDER BY distance
    LIMIT :expanded_limit
  )
  SELECT * FROM ranked ORDER BY distance LIMIT :top_k;
  ```
* **Retour** : tuple `(sql: str, params: dict)` .

<a id="methode-privee-_get_context"></a>

### Méthode privée `_get_context`

```python
@staticmethod
def _get_context(db: Session, chunk_id: int) -> Optional[HierarchicalContext]:
    ...
```

* **But** : pour un chunk donné, remonter récursivement ses parents (niveaux 0–2)
* **Retour** : instanciation de `HierarchicalContext` ou `None` si pas de parent .

---

## Historisation des recherches

Le module intègre un système d'historisation qui enregistre automatiquement toutes les recherches effectuées dans la base de données. Cette fonctionnalité permet:

1. **Mémorisation** des requêtes pour analyse
2. **Calcul de statistiques** sur les comportements de recherche
3. **Génération de rapports** sur les thèmes et termes recherchés

### Schéma de la table `SearchQuery`

```python
class SearchQuery(Base):
    """Historique des recherches utilisateurs."""
    
    __tablename__ = "search_queries"
    
    id = Column(Integer, primary_key=True)
    query_text = Column(String, nullable=False)
    theme = Column(String, nullable=True)
    document_type = Column(String, nullable=True)
    corpus_id = Column(String, nullable=True)
    results_count = Column(Integer, default=0)
    confidence_level = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    user_id = Column(String, nullable=True)  # Pour intégration future d'authentification
```

### Activation de l'historisation

L'historisation est activée **automatiquement** pour toute requête effectuée via la méthode `hybrid_search`. Pour les applications intensives où la performance est critique, elle peut être désactivée via un paramètre de configuration dans le fichier d'environnement:

```bash
LOG_SEARCH_QUERIES=false
```

### Exploitation des données d'historique

Les données historisées peuvent être consultées:

1. Via SQL standard sur la table `search_queries`
2. Via le module de statistiques de Cléa-API (`stats/src/stats_src_compute.py`)
3. Via les endpoints API du tableau de bord admin (`/stats/searches`)

## Exemple d'utilisation avancée

```python
# Requête avec options avancées
req = SearchRequest(
    query="analyse risques climatiques",
    top_k=5,
    theme="RSE",
    filter_by_relevance=True,  # Filtrer les résultats peu pertinents
    normalize_scores=True,     # Normaliser les scores entre 0 et 1
    hierarchical=True,
)

# Exécuter la recherche
response = searcher.hybrid_search(db, req)

# Analyser la confiance dans les résultats
print(f"Confiance: {response.confidence.level:.2f} - {response.confidence.message}")
print(f"Statistiques: min={response.confidence.stats['min']:.2f}, "
      f"max={response.confidence.stats['max']:.2f}, "
      f"avg={response.confidence.stats['avg']:.2f}")

# Vérifier si des résultats ont été trouvés
if not response.results:
    print("Aucun résultat pertinent trouvé")
    if response.confidence.level < 0.3:
        print("La requête semble hors du domaine de connaissances")
else:
    for chunk in response.results:
        print(f"[{chunk.score:.2f}] {chunk.title} → {chunk.content[:60]}…")

# Les données de cette recherche sont automatiquement historisées en base
```

---

## Exemple d'utilisation simple

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from vectordb.src.search import SearchEngine, SearchRequest

# 1. Préparer la session
engine_db = create_engine("postgresql://…")
SessionLocal = sessionmaker(bind=engine_db)
db = SessionLocal()

# 2. Instancier le SearchEngine
searcher = SearchEngine()

# 3. Construire la requête
req = SearchRequest(
    query="analyse risques climatiques",
    top_k=5,
    theme="RSE",
    corpus_id="0207a0ec-394b-475f-912e-edf0315f6fa3",
    hierarchical=True,
)

# 4. Exécuter la recherche
response = searcher.hybrid_search(db, req)

# 5. Parcourir les résultats
for chunk in response.results:
    print(f"[{chunk.score:.2f}] {chunk.title} → {chunk.content[:60]}…")
```

---

> **Voir aussi** : les **endpoints** FastAPI dans `search_endpoint.py`
> – `POST /search/hybrid_search` → renvoie `List[ChunkResult]` .