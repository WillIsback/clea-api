# Bibliothèque de calcul de statistiques (`stats_computer`)

Ce module centralise les calculs de métriques pour l’interface d’administration de Cléa-API.  
Il fournit :

- Des **schemas** Pydantic pour la validation et la sérialisation des résultats.
- Une classe **StatsComputer** pour l’exécution des calculs.

---

## 1. Schemas Pydantic

Tous les modèles utilisent la configuration `CamelConfig` qui génère/transcode automatiquement les clés **snake_case** ↔ **camelCase** 

### 1.1. `DocumentStats`

Représente les métriques sur les documents indexés.

| Attribut         | Type             | Description                                          |
|------------------|------------------|------------------------------------------------------|
| `totalCount`     | `int`            | Nombre total de documents                             |
| `byTheme`        | `Dict[str,int]`  | Répartition des documents par thème                   |
| `byType`         | `Dict[str,int]`  | Répartition des documents par type                     |
| `recentlyAdded`  | `int`            | Nombre de documents ajoutés au cours des 30 derniers jours |
| `percentChange`  | `float`          | Évolution (%) du nombre ajouts par rapport au total    |

### 1.2. `SearchStats`

Métriques sur l’historique des recherches.

| Attribut           | Type                   | Description                                           |
|--------------------|------------------------|-------------------------------------------------------|
| `totalCount`       | `int`                  | Nombre total de recherches                             |
| `lastMonthCount`   | `int`                  | Nombre de recherches au cours du dernier mois          |
| `percentChange`    | `float`                | Évolution (%) entre ce mois et le mois précédent       |
| `topQueries`       | `List[Dict[str,Any]]`  | Liste des requêtes les plus populaires `{query, count}`|

### 1.3. `SystemStats`

Vue d’ensemble de la qualité et de l’état du système.

| Attribut           | Type    | Description                                             |
|--------------------|---------|---------------------------------------------------------|
| `satisfaction`     | `float` | % de recherches jugées satisfaisantes (confiance ≥ 0.7) |
| `avgConfidence`    | `float` | Confiance moyenne sur les recherches du dernier mois    |
| `percentChange`    | `float` | Évolution (%) de la confiance                           |
| `indexedCorpora`   | `int`   | Nombre de corpus déjà indexés                           |
| `totalCorpora`     | `int`   | Nombre total de corpus                                  |

### 1.4. `DashboardStats`

Aggrégation de **DocumentStats**, **SearchStats** et **SystemStats**.

```python
class DashboardStats(BaseModel):
    document_stats: DocumentStats
    search_stats:   SearchStats
    system_stats:   SystemStats
````

---

## 2. Classe `StatsComputer`

Toutes les méthodes retournent les objets Pydantic ci-dessus en interrogeant la base de données via SQLAlchemy.
Initialisation et session :

```python
from stats.src.stats_src_compute import StatsComputer

stats_computer = StatsComputer()
```



### 2.1. `compute_document_stats(skip: int = 0, limit: int = 100) → DocumentStats`

Calcule :

* Nombre total de documents (paginé).
* Répartition par thème et type.
* Nombre de documents ajoutés dans les 30 derniers jours.
* Pourcentage d’évolution.

```python
doc_stats: DocumentStats = stats_computer.compute_document_stats(skip=0, limit=50)
```

### 2.2. `compute_search_stats(skip: int = 0, limit: int = 100) → SearchStats`

Calcule :

* Total des recherches.
* Recherches du dernier mois.
* % d’évolution vs mois précédent.
* Top 10 des requêtes les plus populaires.

```python
search_stats: SearchStats = stats_computer.compute_search_stats(skip=0, limit=200)
```

### 2.3. `compute_system_stats() → SystemStats`

Calcule :

* Confiance moyenne et satisfaction (confiance ≥ 0.7).
* % d’évolution de la confiance.
* Nombre de corpus indexés vs total.

```python
sys_stats: SystemStats = stats_computer.compute_system_stats()
```

### 2.4. `compute_all_stats() → DashboardStats`

Aggrège les trois calculs ci-dessus :

```python
dashboard: DashboardStats = stats_computer.compute_all_stats()
```

---

## 3. Bonnes pratiques

* **Pagination** : Jouez sur `skip`/`limit` pour ne pas surcharger la mémoire.
* **Cache** : En production, stockez les résultats et rafraîchissez-les périodiquement via un job CRON plutôt que d’appeler ces méthodes à chaque requête.
* **Surveillance** : Loggez les appels et la durée d’exécution (`StatsComputer.logger`) pour détecter les goulets d’étranglement.

