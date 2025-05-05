# Schemas Pydantic de Clea-API

Les schémas Pydantic définissent la forme des données échangées avec l’API (requêtes et réponses).  
Tous les modèles utilisent la configuration **`CamelConfig`** pour accepter et produire du **camelCase**.

---

## DocumentCreate

**Payload** minimal pour créer un document (sans contenu).

| Champ          | Type     | Requis | Alias         | Description                            |
| -------------- | -------- | ------ | ------------- | -------------------------------------- |
| `title`        | `string` | Oui    | `title`       | Titre du document.                     |
| `theme`        | `string` | Oui    | `theme`       | Thème du document.                     |
| `document_type`| `string` | Oui    | `documentType`| Type du document (PDF, TXT, etc.).     |
| `publish_date` | `date`   | Oui    | `publishDate` | Date de publication (YYYY-MM-DD).       |
| `corpus_id`    | `string` | Non    | `corpusId`    | UUID du corpus (optionnel).            |

```ts
type DocumentCreate = {
  title: string;
  theme: string;
  documentType: string;
  publishDate: string; // "2025-05-01"
  corpusId?: string;
}
````

---

## ChunkCreate

**Payload** pour créer un chunk (fragment de texte et métadonnées hiérarchiques).

| Champ             | Type      | Requis | Alias            | Description                                                  |
| ----------------- | --------- | ------ | ---------------- | ------------------------------------------------------------ |
| `id`              | `number`  | Non    | `id`             | Identifiant temporaire (uniquement pour hiérarchie interne). |
| `content`         | `string`  | Oui    | `content`        | Contenu textuel du chunk.                                    |
| `start_char`      | `integer` | Oui    | `startChar`      | Position de début dans le texte source (>= 0).               |
| `end_char`        | `integer` | Oui    | `endChar`        | Position de fin dans le texte source (> `startChar`).        |
| `hierarchy_level` | `integer` | Oui    | `hierarchyLevel` | Niveau hiérarchique (0–3).                                   |
| `parent_chunk_id` | `integer` | Non    | `parentChunkId`  | ID du chunk parent (ou `null`).                              |

```ts
type ChunkCreate = {
  id?: number;
  content: string;
  startChar: number;
  endChar: number;
  hierarchyLevel: 0 | 1 | 2 | 3;
  parentChunkId?: number | null;
}
```

---

## DocumentWithChunks

**Payload** complet pour `POST /database/documents`.

| Champ      | Type                                | Requis | Alias      | Description                 |
| ---------- | ----------------------------------- | ------ | ---------- | --------------------------- |
| `document` | [`DocumentCreate`](#DocumentCreate) | Oui    | `document` | Métadonnées du document.    |
| `chunks`   | `ChunkCreate[]`                     | Oui    | `chunks`   | Liste des chunks à insérer. |

```ts
type DocumentWithChunks = {
  document: DocumentCreate;
  chunks: ChunkCreate[];
}
```

---

## DocumentResponse

**Réponse** standard pour toutes les opérations CRUD sur les documents.

| Champ           | Type      | Requis | Alias          | Description                           |
| --------------- | --------- | ------ | -------------- | ------------------------------------- |
| `id`            | `integer` | Oui    | `id`           | Identifiant du document.              |
| `title`         | `string`  | Oui    | `title`        | Titre du document.                    |
| `theme`         | `string`  | Oui    | `theme`        | Thème du document.                    |
| `document_type` | `string`  | Oui    | `documentType` | Type du document.                     |
| `publish_date`  | `date`    | Oui    | `publishDate`  | Date de publication.                  |
| `corpus_id`     | `string`  | Non    | `corpusId`     | UUID du corpus.                       |
| `chunk_count`   | `integer` | Oui    | `chunkCount`   | Nombre de chunks associés (≥ 0).      |
| `index_needed`  | `boolean` | Oui    | `indexNeeded`  | `true` si un nouvel index est requis. |

```ts
type DocumentResponse = {
  id: number;
  title: string;
  theme: string;
  documentType: string;
  publishDate: string;
  corpusId?: string;
  chunkCount: number;
  indexNeeded: boolean;
}
```

---

## DocumentUpdate

**Payload** pour `PUT /database/documents/{id}` (mise à jour).

| Champ           | Type      | Requis | Alias          | Description                              |
| --------------- | --------- | ------ | -------------- | ---------------------------------------- |
| `id`            | `integer` | Oui    | `id`           | Identifiant du document à mettre à jour. |
| `title`         | `string`  | Non    | `title`        | Nouveau titre.                           |
| `theme`         | `string`  | Non    | `theme`        | Nouveau thème.                           |
| `document_type` | `string`  | Non    | `documentType` | Nouveau type de document.                |
| `publish_date`  | `date`    | Non    | `publishDate`  | Nouvelle date de publication.            |
| `corpus_id`     | `string`  | Non    | `corpusId`     | Nouvel UUID de corpus.                   |

```ts
type DocumentUpdate = {
  id: number;
  title?: string;
  theme?: string;
  documentType?: string;
  publishDate?: string;
  corpusId?: string;
}
```

---

## UpdateWithChunks

**Payload** pour `PUT /database/documents/{id}` avec ajout de chunks.

| Champ        | Type             | Requis | Alias       | Description                         |
| ------------ | ---------------- | ------ | ----------- | ----------------------------------- |
| `document`   | `DocumentUpdate` | Oui    | `document`  | Métadonnées à mettre à jour.        |
| `new_chunks` | `ChunkCreate[]`  | Non    | `newChunks` | Liste de nouveaux chunks à ajouter. |

```ts
type UpdateWithChunks = {
  document: DocumentUpdate;
  newChunks?: ChunkCreate[];
}
```

---

## HierarchicalContext

Parents (niveaux 0–2) renvoyés quand `hierarchical=true` en recherche.

| Champ     | Type               | Requis | Alias    | Description                    |
| --------- | ------------------ | ------ | -------- | ------------------------------ |
| `level_0` | `object` or `null` | Non    | `level0` | Chunk de section (lvl 0).      |
| `level_1` | `object` or `null` | Non    | `level1` | Chunk de sous-section (lvl 1). |
| `level_2` | `object` or `null` | Non    | `level2` | Chunk de paragraphe (lvl 2).   |

---

## ChunkResult

Un chunk renvoyé par `POST /search/hybrid_search`.

| Champ             | Type                            | Requis | Alias            | Description                              |
| ----------------- | ------------------------------- | ------ | ---------------- | ---------------------------------------- |
| `chunk_id`        | `integer`                       | Oui    | `chunkId`        | Identifiant du chunk.                    |
| `document_id`     | `integer`                       | Oui    | `documentId`     | ID du document parent.                   |
| `title`           | `string`                        | Oui    | `title`          | Titre du document parent.                |
| `content`         | `string`                        | Oui    | `content`        | Contenu du chunk.                        |
| `theme`           | `string`                        | Oui    | `theme`          | Thème du document.                       |
| `document_type`   | `string`                        | Oui    | `documentType`   | Type du document.                        |
| `publish_date`    | `date`                          | Oui    | `publishDate`    | Date de publication.                     |
| `score`           | `number`                        | Oui    | `score`          | Score de similarité (distance ou score). |
| `hierarchy_level` | `integer`                       | Oui    | `hierarchyLevel` | Niveau hiérarchique (0–3).               |
| `context`         | `HierarchicalContext` or `null` | Non    | `context`        | Contexte parent (facultatif).            |

---

## SearchRequest

**Paramètres pour la recherche hybride.**  
Combine la requête textuelle avec des filtres de métadonnées optionnels.

| Champ                 | Type      | Requis | Alias               | Description                                    |
| --------------------- | --------- | ------ | ------------------- | ---------------------------------------------- |
| `query`               | `string`  | Oui    | `query`             | Requête en langage naturel.                   |
| `top_k`               | `integer` | Non    | `topK`              | Nombre de résultats à retourner (défaut 10).  |
| `theme`               | `string`  | Non    | `theme`             | Filtre par thème.                              |
| `document_type`       | `string`  | Non    | `documentType`      | Filtre par type de document.                   |
| `start_date`          | `date`    | Non    | `startDate`         | Date de début.                                 |
| `end_date`            | `date`    | Non    | `endDate`           | Date de fin.                                   |
| `corpus_id`           | `integer` | Non    | `corpusId`          | ID du corpus.                                  |
| `hierarchy_level`     | `integer` | Non    | `hierarchyLevel`    | Niveau hiérarchique (0–2).                     |
| `hierarchical`        | `boolean` | Non    | `hierarchical`      | Récupérer le contexte hiérarchique.            |
| `filter_by_relevance` | `boolean` | Non    | `filterByRelevance` | Filtrer les résultats sous le seuil de pertinence. |
| `normalize_scores`    | `boolean` | Non    | `normalizeScores`   | Normaliser les scores entre 0 et 1.            |

---

## SearchResponse

**Réponse à une requête de recherche.**  
Contient les résultats triés par pertinence avec métadonnées et évaluation de confiance.

| Champ           | Type                | Requis | Alias          | Description                                    |
| --------------- | ------------------- | ------ | -------------- | ---------------------------------------------- |
| `query`         | `string`            | Oui    | `query`        | Requête originale.                             |
| `top_k`         | `integer`           | Oui    | `topK`         | Nombre de résultats demandés.                  |
| `total_results` | `integer`           | Oui    | `totalResults` | Nombre total de résultats trouvés.             |
| `results`       | `ChunkResult[]`     | Oui    | `results`      | Résultats de la recherche.                     |
| `confidence`    | `ConfidenceMetrics` | Non    | `confidence`   | Métriques de confiance sur les résultats.      |
| `normalized`    | `boolean`           | Non    | `normalized`   | Indique si les scores sont normalisés (0–1).   |
| `message`       | `string`            | Non    | `message`      | Message informatif sur les résultats.          |

---

## ConfidenceMetrics

Métriques de confiance et statistiques pour évaluer la pertinence des résultats.

| Champ     | Type        | Requis | Alias     | Description                                        |
| --------- | ----------- | ------ | --------- | -------------------------------------------------- |
| `level`   | `float`     | Oui    | `level`   | Niveau de confiance entre 0 et 1.                  |
| `message` | `string`    | Oui    | `message` | Message explicatif sur la qualité des résultats.   |
| `stats`   | `object`    | Oui    | `stats`   | Statistiques sur les scores.                       |

Exemple de `stats`:

```json
{
  "min": -5.89,
  "max": 1.23,
  "avg": -0.45,
  "median": -0.12
}
```

---

## IndexStatus

Statut d’indexation d’un corpus.

| Champ            | Type      | Requis | Alias           | Description                                            |
| ---------------- | --------- | ------ | --------------- | ------------------------------------------------------ |
| `corpus_id`      | `string`  | Oui    | `corpusId`      | UUID du corpus interrogé.                              |
| `index_exists`   | `boolean` | Oui    | `indexExists`   | `true` si l’index physique existe en base.             |
| `config_exists`  | `boolean` | Oui    | `configExists`  | `true` si la config SQLAlchemy (`IndexConfig`) existe. |
| `is_indexed`     | `boolean` | Oui    | `isIndexed`     | `true` si la config est marquée indexée.               |
| `index_type`     | `string`  | Non    | `indexType`     | Type d’index (`ivfflat`, `hnsw`).                      |
| `chunk_count`    | `integer` | Oui    | `chunkCount`    | Nombre total de chunks dans le corpus.                 |
| `indexed_chunks` | `integer` | Oui    | `indexedChunks` | Nombre de chunks effectivement indexés.                |
| `last_indexed`   | `date`    | Non    | `lastIndexed`   | Date du dernier index (ou `null`).                     |

---

> Tous les modèles se trouvent dans `vectordb/src/schemas.py`&#x20;
> Dernière mise à jour : **03 mai 2025**.
