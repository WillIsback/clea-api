
# Intégration JavaScript / TypeScript – Gestion des index vectoriels

Ce guide explique comment gérer les index **IVFFLAT** / **HNSW** de **Vectordb** depuis JavaScript ou TypeScript, en appelant directement les endpoints FastAPI 

---

## 1. Configuration du client

```ts
import axios from 'axios';

export const API_URL = process.env.CLEA_API ?? 'http://localhost:8080';

export const idxClient = axios.create({
  baseURL: `${API_URL}/index`,
  headers: { 'Content-Type': 'application/json' },
});
````

---

## 2. Types TypeScript

```ts
export interface IndexSimpleResult {
  status: 'ok' | 'error';
  message: string;
}

export interface IndexStatus {
  corpusId: string;
  indexExists: boolean;
  configExists: boolean;
  isIndexed: boolean;
  indexType: string;
  chunkCount: number;
  indexedChunks: number;
  lastIndexed: string | null;
}

export interface AllIndexesStatus {
  [corpusId: string]: IndexStatus;
}
```

---

## 3. Créer un index pour un corpus

```ts
export async function createIndex(
  corpusId: string
): Promise<IndexSimpleResult> {
  const res = await idxClient.post(`/create-index/${corpusId}`);
  if (!res.status.toString().startsWith('2')) {
    throw new Error(`Create index failed: ${res.status}`);
  }
  return res.data as IndexSimpleResult;
}

// Exemple d’usage
createIndex('ae12f3e4-5678-90ab-cdef-1234567890ab')
  .then(r => console.log('Index créé:', r.message))
  .catch(console.error);
```

---

## 4. Supprimer un index

```ts
export async function dropIndex(
  corpusId: string
): Promise<IndexSimpleResult> {
  const res = await idxClient.delete(`/drop-index/${corpusId}`);
  if (!res.status.toString().startsWith('2')) {
    throw new Error(`Drop index failed: ${res.status}`);
  }
  return res.data as IndexSimpleResult;
}

// Exemple d’usage
dropIndex('ae12f3e4-5678-90ab-cdef-1234567890ab')
  .then(r => console.log('Index supprimé:', r.message))
  .catch(console.error);
```

---

## 5. Vérifier l’état d’un index

```ts
export async function getIndexStatus(
  corpusId: string
): Promise<IndexStatus> {
  const res = await idxClient.get<IndexStatus>(`/index-status/${corpusId}`);
  return res.data;
}

// Exemple d’usage
getIndexStatus('ae12f3e4-5678-90ab-cdef-1234567890ab')
  .then(status => {
    console.log(`Index exists: ${status.isIndexed}, type: ${status.indexType}`);
  })
  .catch(console.error);
```

---

## 6. Vérifier tous les index

```ts
export async function getAllIndexes(): Promise<AllIndexesStatus> {
  const res = await idxClient.get('/indexes');
  return res.data as AllIndexesStatus;
}

// Exemple d’usage
getAllIndexes()
  .then(all => console.table(all))
  .catch(console.error);
```

---

> Pour plus de détails, voir les routes définies dans `api/index_endpoint.py` et les DTO Pydantic dans `src/schemas.py`&#x20;
> Guide généré automatiquement — 05 mai 2025

