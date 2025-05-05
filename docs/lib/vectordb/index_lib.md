# Module `index_manager`

Gestion des index vectoriels pour pgvector au sein de **Cléa-API**.  
Ce module offre une API simple pour créer, supprimer et contrôler l'état des index IVFFLAT associés aux chunks de documents.

---

## Installation

Le module `index_manager` fait partie du package `vectordb`.  
Aucun paquet externe n'est nécessaire, si ce n'est votre installation PostgreSQL/pgvector et SQLAlchemy.

```bash
uv pip install vectordb
```

---

## Table des matières

1. [Créer un index simple](#create_simple_index)
2. [Supprimer un index](#drop_index)
3. [Vérifier l'état d'un index](#check_index_status)
4. [Vérifier tous les index](#check_all_indexes)
5. [Nettoyer les index orphelins](#clean_orphaned_indexes)
6. [Programmation du nettoyage automatique](#schedule_cleanup_job)

---

<a name="create_simple_index"></a>

## 1. `create_simple_index(corpus_id: str) → dict`

Crée un index **IVFFLAT** standard sur une vue matérialisée des chunks appartenant au corpus.

```python
from vectordb.src.index_manager import create_simple_index

result = create_simple_index("3159e84e-9dc6-41a7-a464-bb6c3894a5ad")
print(result)
```

| Paramètre   | Type  | Description                             |
| ----------- | ----- | --------------------------------------- |
| `corpus_id` | `str` | UUID du corpus à indexer (avec tirets). |

**Retourne** un dictionnaire comportant :

* `status`: `"success"`, `"exists"` ou `"error"`.
* `message`: message human-readable.
* Sur succès :

  * `index_type`: toujours `"ivfflat"`.
  * `lists`: nombre de listes utilisées pour IVFFLAT.
  * `documents_updated`: nombre de documents flagués `index_needed=False`.
  * `view_name`: nom de la vue matérialisée créée.

<details>
<summary>Exemple de sortie</summary>

```json
{
  "status": "success",
  "message": "Index vectoriel créé pour 123 chunks dans le corpus 3159e84e-9dc6-41a7-a464-bb6c3894a5ad",
  "index_type": "ivfflat",
  "lists": 11,
  "documents_updated": 42,
  "view_name": "temp_corpus_chunks_3159e84e_9dc6_41a7_a464_bb6c3894a5ad"
}
```

</details>

---

<a name="drop_index"></a>

## 2. `drop_index(corpus_id: str) → dict`

Supprime l'index et la vue matérialisée correspondant au corpus.

```python
from vectordb.src.index_manager import drop_index

result = drop_index("3159e84e-9dc6-41a7-a464-bb6c3894a5ad")
print(result)
```

| Paramètre   | Type  | Description                                    |
| ----------- | ----- | ---------------------------------------------- |
| `corpus_id` | `str` | UUID du corpus dont on veut supprimer l'index. |

**Retourne** :

* `status`: `"success"`, `"warning"` (si l'index n'existait pas) ou `"error"`.
* `message`: explication de l'opération.

<details>
<summary>Exemple de sortie</summary>

```json
{
  "status": "success",
  "message": "Index idx_vector_3159e84e_9dc6_41a7_a464_bb6c3894a5ad et vue temp_corpus_chunks_3159e84e_9dc6_41a7_a464_bb6c3894a5ad supprimés avec succès"
}
```

</details>

---

<a name="check_index_status"></a>

## 3. `check_index_status(corpus_id: str) → dict`

Récupère l'état courant de l'index vectoriel pour un corpus donné.

```python
from vectordb.src.index_manager import check_index_status

status = check_index_status("3159e84e-9dc6-41a7-a464-bb6c3894a5ad")
print(status)
```

| Paramètre   | Type  | Description     |
| ----------- | ----- | --------------- |
| `corpus_id` | `str` | UUID du corpus. |

**Retourne** un objet contenant :

* `corpus_id` : UUID interrogé.
* `index_exists` : booléen, l'index existe-t-il en base ?
* `config_exists` : booléen, la config Pydantic/SQLAlchemy existe-t-elle ?
* `is_indexed` : booléen, l'index est-il actif selon la config ?
* `index_type` : `"ivfflat"` ou `"hnsw"` ou `null`.
* `chunk_count` : nombre total de chunks dans le corpus.
* `indexed_chunks` : nombre de chunks réellement indexés (config).
* `last_indexed` : date du dernier indexe (`datetime`) ou `null`.

<details>
<summary>Exemple de sortie</summary>

```json
{
  "corpus_id": "3159e84e-9dc6-41a7-a464-bb6c3894a5ad",
  "index_exists": true,
  "config_exists": true,
  "is_indexed": true,
  "index_type": "ivfflat",
  "chunk_count": 123,
  "indexed_chunks": 123,
  "last_indexed": "2025-05-02T14:23:10.123456"
}
```

</details>

---

<a name="check_all_indexes"></a>

## 4. `check_all_indexes() → dict`

Balaye tous les corpus en base et renvoie l'état de leurs index.

```python
from vectordb.src.index_manager import check_all_indexes

all_status = check_all_indexes()
print(all_status)
```

**Retourne** :

* `status`: `"success"` ou `"error"`.
* `corpus_count`: nombre de corpus trouvés.
* `indexes`: tableau d'objets identiques à la sortie de `check_index_status()`.

<details>
<summary>Exemple de sortie</summary>

```json
{
  "status": "success",
  "corpus_count": 3,
  "indexes": [
    {
      "corpus_id": "aaa111...",
      "index_exists": true,
      "config_exists": true,
      "is_indexed": true,
      "index_type": "ivfflat",
      "chunk_count": 200,
      "indexed_chunks": 200,
      "last_indexed": "2025-05-01T09:12:34"
    },
    {
      "corpus_id": "bbb222...",
      "index_exists": false,
      "config_exists": false,
      "is_indexed": false,
      "index_type": null,
      "chunk_count": 0,
      "indexed_chunks": 0,
      "last_indexed": null
    }
  ]
}
```

</details>

---

<a name="clean_orphaned_indexes"></a>

## 5. `clean_orphaned_indexes() → dict`

Nettoie les index et configurations orphelins qui ne sont plus associés à des corpus existants.

Cette fonction est utile pour maintenir la propreté de la base de données après la suppression de documents :
- Elle identifie les configurations d'index dont le corpus n'existe plus
- Elle supprime les vues matérialisées et index PostgreSQL associés
- Elle nettoie les entrées dans la table `index_configs`

```python
from vectordb.src.index_cleaner import clean_orphaned_indexes

result = clean_orphaned_indexes()
print(result)
```

**Retourne** un dictionnaire comportant :

* `status`: `"success"`, `"partial_success"` (certaines suppressions ont échoué) ou `"error"`.
* `deleted_count`: nombre de configurations d'index supprimées.
* `cleaned_corpus_ids`: liste des identifiants de corpus nettoyés.
* `errors`: liste d'erreurs éventuelles lors du nettoyage (si `partial_success`).
* `timestamp`: horodatage de l'opération.

<details>
<summary>Exemple de sortie</summary>

```json
{
  "status": "success",
  "deleted_count": 2,
  "cleaned_corpus_ids": [
    "cccc111-dddd-eeee-ffff-gggghhhhiiii",
    "jjjj222-kkkk-llll-mmmm-nnnnoooooppp"
  ],
  "errors": [],
  "timestamp": "2025-05-05T10:30:45.123456"
}
```

</details>

---

<a name="schedule_cleanup_job"></a>

## 6. `schedule_cleanup_job(interval_hours: int = 24) → None`

Configure un travail périodique qui nettoie automatiquement les index orphelins.

Cette fonction utilise APScheduler pour exécuter `clean_orphaned_indexes` à intervalles réguliers.
Elle est généralement appelée au démarrage de l'application via la lifespan FastAPI.

```python
from vectordb.src.index_cleaner import schedule_cleanup_job

# Configurer un nettoyage toutes les 12 heures
schedule_cleanup_job(interval_hours=12)
```

| Paramètre        | Type  | Description                           | Défaut |
| ---------------- | ----- | ------------------------------------- | ------ |
| `interval_hours` | `int` | Intervalle en heures entre nettoyages | `24`   |

**Exemple d'intégration dans la lifespan FastAPI** :

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from vectordb.src.index_cleaner import schedule_cleanup_job

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage de l'application
    schedule_cleanup_job(interval_hours=24)
    yield
    # Arrêt de l'application - rien à faire car APScheduler s'arrête automatiquement

app = FastAPI(lifespan=lifespan)
```

---

## Logging & erreurs

* Toutes les opérations journalisent en niveau **INFO** et **WARNING** via le logger standard.
* En cas d'erreur, la transaction est roll-backée et `{"status":"error","message":...}` est retourné.
* Le nettoyage des index orphelins génère des logs détaillés pour faciliter le suivi des opérations.

---

> *Modules* : `vectordb/src/index_manager.py`, `vectordb/src/index_cleaner.py`  
> *Dernière mise à jour* : 05 mai 2025