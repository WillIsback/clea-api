# Module `crud`

Ce module fournit des opérations CRUD de haut niveau sur les entités **Document**, **Chunk** et **IndexConfig**, avec gestion des embeddings et des index pgvector.  

Fichier source : `vectordb/src/crud.py` :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}

---

## Installation

Ce module est inclus dans le package `vectordb`. Pour l’installer :

```bash
pip install vectordb
````

---

## Table des matières

1. [add\_document\_with\_chunks](#add_document_with_chunks)
2. [update\_document\_with\_chunks](#update_document_with_chunks)
3. [delete\_document\_chunks](#delete_document_chunks)
4. [delete\_document](#delete_document)

---

<a name="add_document_with_chunks"></a>

## 1. `add_document_with_chunks(db, doc, chunks, batch_size=10) → Dict[str, Any]`

Ajoute un **document** et ses **chunks** en base, génère les embeddings en lot, et gère la configuration de l’index.

```python
from sqlalchemy.orm import Session
from vectordb.src.schemas import DocumentCreate
from vectordb.src.crud import add_document_with_chunks

result = add_document_with_chunks(db: Session, doc: DocumentCreate, chunks: List[dict], batch_size=20)
```

### Description

* Génère `corpus_id` si manquant.
* Insère le document (`Document`) avec un flag `index_needed`.
* Pour chaque lot de `batch_size` chunks :

  * Calcule les embeddings via `EmbeddingGenerator.generate_embeddings_batch`.
  * Insère les objets `Chunk` (avec flush intermédiaires).
  * Construit les relations parent↔enfant.
* Met à jour ou crée la configuration d’index (`IndexConfig`).
* Commit ou rollback en cas d’erreur.

### Paramètres

| Nom          | Type              | Description                                           |
| ------------ | ----------------- | ----------------------------------------------------- |
| `db`         | `Session`         | Session SQLAlchemy active.                            |
| `doc`        | `DocumentCreate`  | Métadonnées du document à créer.                      |
| `chunks`     | `List[dict]`      | Liste de chunks `{ content, hierarchy_level, ... }`.  |
| `batch_size` | `int` (défaut 10) | Taille des sous-lots pour la génération d’embeddings. |

### Retour

```json
{
  "document_id": int,
  "chunks": int,
  "corpus_id": str,
  "index_needed": bool
}
```

* `index_needed = True` si un nouvel index doit être (re)créé.&#x20;

---

<a name="update_document_with_chunks"></a>

## 2. `update_document_with_chunks(document_update, new_chunks=None) → Dict[str, Any]`

Met à jour un document existant et ajoute éventuellement de nouveaux chunks.

```python
from vectordb.src.schemas import DocumentUpdate
from vectordb.src.crud import update_document_with_chunks

result = update_document_with_chunks(
    document_update: DocumentUpdate,
    new_chunks: List[dict]  # facultatif
)
```

### Description

* Charge le `Document` par son `id`.
* Met à jour les champs fournis (`title`, `theme`, etc.).
* Si `new_chunks` est fourni :

  * Calcule les embeddings un par un.
  * Insère en bulk via `insert(Chunk)`.
  * Met à jour le compteur `chunk_count` dans `IndexConfig`.
* Si `corpus_id` change, ajuste les compteurs sur les anciennes/nouvelles configurations d’index.
* Retourne les métadonnées mises à jour et si `index_needed` suite à un changement de corpus.

### Paramètres

| Nom               | Type                     | Description                                     |
| ----------------- | ------------------------ | ----------------------------------------------- |
| `document_update` | `DocumentUpdate`         | DTO avec l’`id` du document et champs modifiés. |
| `new_chunks`      | `List[dict]` (optionnel) | Nouveaux chunks à ajouter.                      |

### Retour

```json
{
  "id": int,
  "title": str,
  "theme": str,
  "document_type": str,
  "publish_date": date,
  "corpus_id": str,
  "chunks": { "total": int, "added": int },
  "index_needed": bool
}
```

En cas de document introuvable : `{"error": "… introuvable."}`&#x20;

---

<a name="delete_document_chunks"></a>

## 3. `delete_document_chunks(document_id, chunk_ids=None) → Dict[str, Any]`

Supprime un ou plusieurs chunks d’un document, ou tous si `chunk_ids` non fourni.

```python
from vectordb.src.crud import delete_document_chunks

result = delete_document_chunks(document_id: int, chunk_ids: Optional[List[int]])
```

### Description

* Vérifie l’existence du `Document`.
* Si `chunk_ids` est une liste :

  * Supprime uniquement ces chunks.
* Sinon :

  * Supprime tous les chunks associés.
* Met à jour `chunk_count` dans `IndexConfig`.
* Commit ou rollback en cas d’erreur.

### Paramètres

| Nom           | Type                    | Description                                      |
| ------------- | ----------------------- | ------------------------------------------------ |
| `document_id` | `int`                   | Identifiant du document.                         |
| `chunk_ids`   | `List[int]` (optionnel) | Liste d’IDs de chunks à supprimer (None → tous). |

### Retour

```json
{
  "document_id": int,
  "chunks_deleted": int,
  "remaining_chunks": int
}
```

Remarque : si document introuvable → `{"error": "… introuvable."}`&#x20;

---

<a name="delete_document"></a>

## 4. `delete_document(document_id) → Dict[str, Any]`

Supprime un document et tous ses chunks en cascade.

```python
from vectordb.src.crud import delete_document

result = delete_document(document_id: int)
```

### Description

* Charge le `Document` par `id`.
* Met à jour `chunk_count` dans la configuration d’index (diminue du nombre de chunks supprimés).
* Supprime le document (cascade supprime les chunks).
* Commit ou rollback en cas d’erreur.

### Paramètres

| Nom           | Type  | Description                          |
| ------------- | ----- | ------------------------------------ |
| `document_id` | `int` | Identifiant du document à supprimer. |

### Retour

* En cas de succès :

  ```json
  { "success": "Document avec ID X supprimé avec succès." }
  ```
* Si introuvable :

  ````json
  { "error": "Document avec ID X introuvable." }
  ``` :contentReference[oaicite:8]{index=8}:contentReference[oaicite:9]{index=9}
  ````

---

> Module : `vectordb/src/crud.py`
> Dernière mise à jour : 02 mai 2025
