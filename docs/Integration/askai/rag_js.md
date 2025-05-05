# Intégration **JavaScript / TypeScript** — Ask-AI (RAG)

Ce guide montre comment interroger le service **RAG** (Retrieve-and-Generate) via les endpoints **`/ask`** et **`/models`** 
> Les exemples utilisent **`fetch`** natif (Node 18+) ou navigateur moderne.

---

## Pré-requis

```bash
npm install cross-fetch   # polyfill fetch pour Node <18
npm install -D typescript # pour typer
````

Définissez l’URL :

```ts
export const CLEA_API = process.env.CLEA_API ?? "http://localhost:8080";
```

---

## Types TypeScript

```ts
/** Payload pour /ask */
export interface AskRequest {
  query: string;
  filters?: Record<string, any>;
  theme?: string;
  modelName?: string;      // ex: "Qwen3-0.6B"
  stream?: boolean;
  promptType?: string;     // "standard" | "summary" | "comparison"
  enableThinking?: boolean;
}

/** Réponse standard non-streamée */
export interface AskResponse {
  response: string;
  context: any[];          // tableau de chunks/metadata (voir vectordb SearchResponse)
  thinking?: string;       // présent si enableThinking=true
}

/** Liste des modèles disponibles */
export interface ModelsResponse {
  models: string[];
}
```

---

## 1. Récupérer la liste des modèles

```ts
export async function getModels(): Promise<string[]> {
  const res = await fetch(`${CLEA_API}/ask/models`);
  if (!res.ok) throw new Error(`Failed to fetch models: ${await res.text()}`);
  const data: ModelsResponse = await res.json();
  return data.models;
}

/* Exemple */
const models = await getModels();
console.log("Modèles disponibles :", models);
```

---

## 2. Poser une question (non-streaming)

```ts
export async function askAI(
  req: AskRequest
): Promise<AskResponse> {
  const res = await fetch(`${CLEA_API}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`ASK failed: ${await res.text()}`);
  return res.json();
}

/* Exemple */
const answer = await askAI({
  query: "Qu'est-ce qu'un RAG system ?",
  theme: "Informatique",
  modelName: "Qwen3-0.6B",
  stream: false,
  promptType: "standard",
});
console.log("Réponse :", answer.response);
console.table(answer.context);
```

<details>
<summary>📜 Log réel (extrait)</summary>

```json
{
  "response": "Un système RAG combine la recherche documentaire…",
  "context": [
    { "chunkId": 5, "documentId": 3, "score": 0.12, … },
    …
  ]
}
```

</details>

---

## 3. Poser une question (streaming SSE)

```ts
export function askAIStream(
  req: AskRequest,
  onData: (chunk: any) => void
) {
  // NOTE : vous pouvez utiliser EventSource si exposé en SSE,
  // ou fetch + ReadableStream pour Node 18+.
  const evtSource = new EventSource(`${CLEA_API}/ask?${new URLSearchParams({
    stream: "true"
  })}`, { withCredentials: true });
  evtSource.onmessage = (e) => {
    if (e.data === "[DONE]") {
      evtSource.close();
    } else {
      onData(JSON.parse(e.data));
    }
  };
}

/* Exemple */
askAIStream({ query: "Explique RAG", stream: true }, (chunk) => {
  console.log("→", chunk);
});
```

---

## Bonnes pratiques

* **Timeout** : mettez en place un timeout front-end pour les streams longue durée.
* **Retry** : implémentez un back-off sur `502` / `503`.
* **Throttling** : protégez le service contre trop de requêtes simultanées.

