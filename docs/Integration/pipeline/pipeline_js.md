# Intégration **JavaScript / TypeScript** — Doc Loader

Ce guide montre comment appeler l’endpoint **`/doc_loader/upload-file`** pour uploader un fichier et récupérer ses chunks extraits

> Les exemples utilisent **`fetch`** natif (Node 18+) ou navigateur moderne.  
> Pour Node < 18, installez un polyfill :

```bash
npm install cross-fetch
```

---

## Pré-requis

```bash
npm install cross-fetch   # polyfill fetch pour Node <18
npm install -D typescript # si vous souhaitez typer
````

Définissez l’URL de l’API :

```ts
export const CLEA_API = process.env.CLEA_API ?? "http://localhost:8080";
```

---

## Types TypeScript

```ts
/** Chunk brut extrait d’un document */
export interface ExtractedDocument {
  title: string;
  content: string;
  theme: string;
  documentType: string;
  publishDate: string;  // ISO (YYYY-MM-DD)
  embedding?: string | null;
}
```

---

## Uploader un fichier et récupérer les chunks

```ts
export async function uploadFile(
  file: File,
  maxLength = 1000,
  theme = "Thème générique"
): Promise<ExtractedDocument[]> {
  // Préparer le formulaire
  const form = new FormData();
  form.append("file", file);
  form.append("max_length", maxLength.toString());
  form.append("theme", theme);

  // Appeler l'endpoint
  const res = await fetch(`${CLEA_API}/doc_loader/upload-file`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error(`Upload failed: ${await res.text()}`);
  }
  return res.json();
}
```

### Exemple rapide

```ts
const input = document.querySelector<HTMLInputElement>("#fileInput")!;
const file = input.files![0];
const docs = await uploadFile(file, 2000, "Finance");
console.log("Chunks reçus :", docs.length);
docs.forEach((d, i) =>
  console.log(`#${i + 1}`, d.title, d.content.slice(0, 50) + "…")
);
```

<details>
<summary>📜 Log réel (extrait)</summary>

```json
[
  {
    "title": "demo.txt",
    "content": "Ligne 1\nLigne 2\n…",
    "theme": "Finance",
    "documentType": "TXT",
    "publishDate": "2025-05-01",
    "embedding": null
  },
  {
    "title": "demo.txt (part 2)",
    "content": "Suite du document…",
    "theme": "Finance",
    "documentType": "TXT",
    "publishDate": "2025-05-01",
    "embedding": null
  }
]
```

</details>

---

## Bonnes pratiques

* **Taille des chunks** : ajustez `max_length` selon la granularité souhaitée.
* **Nettoyage** : supprimez les fichiers temporaires côté client si nécessaire.
* **Gestion des erreurs** : surveillez les codes `4xx` / `5xx` et affichez `res.statusText` ou `await res.text()`.
