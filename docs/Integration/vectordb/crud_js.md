<!-- File: docs/Integration/vectordb/crud_js.md -->

# Intégration JavaScript / TypeScript – Vectordb CRUD

Ce guide montre comment appeler les endpoints CRUD de **Vectordb** (/database) depuis un client JavaScript ou TypeScript, en s’appuyant sur les schémas Pydantic et les routes FastAPI 

---

## 1. Configuration du client

```ts
import axios from 'axios';

export const API_URL = process.env.CLEA_API ?? 'http://localhost:8080';

export const dbClient = axios.create({
  baseURL: `${API_URL}/database`,
  headers: { 'Content-Type': 'application/json' },
});
````

---

## 2. Types TypeScript

```ts
/* schémas HTTP (Pydantic → TS) */
export interface DocumentCreate {
  title: string;
  theme: string;
  document_type: string;
  publish_date: string;      // ISO (YYYY-MM-DD)
  corpus_id?: string | null;
}

export interface ChunkCreate {
  id?: number;
  content: string;
  start_char: number;
  end_char: number;
  hierarchy_level: number;
  parent_chunk_id?: number | null;
}

export interface DocumentWithChunks {
  document: DocumentCreate;
  chunks: ChunkCreate[];
}

export interface DocumentResponse {
  id: number;
  title: string;
  theme: string;
  document_type: string;
  publish_date: string;
  corpus_id: string | null;
  chunk_count: number;
  index_needed: boolean;
}

export interface UpdateWithChunks {
  document: { id: number } & Partial<DocumentCreate>;
  new_chunks?: ChunkCreate[];
}
```

---

## 3. Ajouter un document + chunks

```ts
export async function addDocument(
  payload: DocumentWithChunks
): Promise<DocumentResponse> {
  const res = await dbClient.post('/documents', payload);
  if (!res.status.toString().startsWith('2')) {
    throw new Error(`Add failed: ${res.status} ${res.statusText}`);
  }
  return res.data as DocumentResponse;
}

// Exemple d’usage
const payload: DocumentWithChunks = {
  document: {
    title: 'Rapport Q2 2025',
    theme: 'Finance',
    document_type: 'PDF',
    publish_date: '2025-06-30',
  },
  chunks: [
    { content: 'Résumé…', start_char: 0, end_char: 100, hierarchy_level: 3 },
    { content: 'Détails…', start_char: 101, end_char: 300, hierarchy_level: 3 },
  ],
};

addDocument(payload)
  .then(doc => console.log('Créé ID ➜', doc.id, 'avec', doc.chunk_count, 'chunks'))
  .catch(console.error);
```

---

## 4. Mettre à jour un document

```ts
export async function updateDocument(
  id: number,
  patch: Partial<DocumentCreate>,
  newChunks: ChunkCreate[] = []
): Promise<DocumentResponse> {
  const payload: UpdateWithChunks = {
    document: { id, ...patch },
    new_chunks: newChunks.length ? newChunks : undefined,
  };
  const res = await dbClient.put(`/documents/${id}`, payload);
  if (!res.status.toString().startsWith('2')) {
    throw new Error(`Update failed: ${res.status}`);
  }
  return res.data as DocumentResponse;
}

// Exemple d’usage
updateDocument(1, { title: 'Titre mis à jour' }, [
  { content: 'Nouveau chunk', start_char: 300, end_char: 350, hierarchy_level: 3 },
])
  .then(doc => console.log('Mis à jour ➜', doc))
  .catch(console.error);
```

---

## 5. Supprimer un document ou ses chunks

```ts
// Supprimer tout le document
export async function deleteDocument(id: number): Promise<void> {
  const res = await dbClient.delete(`/documents/${id}`);
  if (res.status !== 200) throw new Error(`Delete doc failed: ${res.status}`);
}

// Supprimer des chunks spécifiques
export async function deleteChunks(
  documentId: number,
  chunkIds: number[]
): Promise<{ document_id: number; chunks_deleted: number; remaining_chunks: number }> {
  const params = chunkIds.map(id => `chunk_ids=${id}`).join('&');
  const res = await dbClient.delete(`/documents/${documentId}/chunks?${params}`);
  if (res.status !== 200) throw new Error(`Delete chunks failed: ${res.status}`);
  return res.data;
}

// Exemple d’usage
deleteChunks(2, [5, 6])
  .then(info => console.log('Chunks supprimés ➜', info.chunks_deleted))
  .catch(console.error);
```

---

## 6. Lister & récupérer

```ts
// Lister avec pagination et filtres
export async function listDocuments(
  filters: { theme?: string; document_type?: string; corpus_id?: string },
  skip = 0,
  limit = 50
): Promise<DocumentResponse[]> {
  const res = await dbClient.get('/documents', {
    params: { ...filters, skip, limit }
  });
  return res.data as DocumentResponse[];
}

// Récupérer un document par ID
export async function getDocument(id: number): Promise<DocumentResponse> {
  const res = await dbClient.get(`/documents/${id}`);
  return res.data as DocumentResponse;
}

// Récupérer les chunks d’un document
export async function getDocumentChunks(
  documentId: number,
  params: { hierarchyLevel?: number; parentChunkId?: number; skip?: number; limit?: number } = {}
): Promise<ChunkCreate[]> {
  const res = await dbClient.get(`/documents/${documentId}/chunks`, {
    params: { ...params }
  });
  return res.data as ChunkCreate[];
}

// Exemple d’usage
listDocuments({ theme: 'Finance' }, 0, 10)
  .then(docs => docs.forEach(d => console.log(d.id, d.title)))
  .catch(console.error);
```

---

> Pour plus de détails sur les schémas et les réponses, voir `src/schemas.py` et `api/database_endpoint.py`&#x20;
> Guide généré automatiquement — 05 mai 2025


