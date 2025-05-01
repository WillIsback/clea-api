# Cléa-API 🚀  

*Hybrid document-search framework for PostgreSQL + pgvector*

[![Licence MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-ReadTheDocs-green.svg)](https://<your-gh-user>.github.io/clea-api)

Cléa-API charge des documents multi-formats, les segmente, les vectorise et
fournit une **recherche hybride (vectorielle + filtres SQL)** prête à l’emploi.
Il s’utilise :

* via **endpoints REST** (FastAPI) ;
* en **librairie Python** (extraction, pipeline, recherche) ;
* avec une **base PostgreSQL + pgvector** auto-indexée par corpus.

---

## Sommaire rapide

| Sujet | Lien |
|-------|------|
| Docs HTML (MkDocs) | <https://WillIsback.github.io/clea-api> |
| Structure & concepts | [`docs/index.md`](docs/index.md) |
| Guide d’extraction | [`docs/doc_loader.md`](docs/doc_loader.md) |
| Base de données & index | [`docs/database.md`](docs/database.md) |
| Recherche hybride | [`docs/search.md`](docs/search.md) |
| Pipeline end-to-end | [`docs/pipeline.md`](docs/pipeline.md) |

> **Important :** le présent README n’est pas compilé par MkDocs ;  
> il contient donc seulement les informations de démarrage.
> La documentation complète vit dans le dossier `docs/`.

---

## Caractéristiques clés

- 🔄 **Chargement multi-formats** : PDF, DOCX, HTML, JSON, TXT, …  
- 🧩 **Segmentation hiérarchique** : Section ▶ Paragraphe ▶ Chunk.  
- 🔍 **Recherche hybride** : *ivfflat* ou *HNSW* + Cross-Encoder rerank.  
- ⚡ **Pipeline “one-liner”** :  

  ```python
  from pipeline import process_and_store
  process_and_store("rapport.pdf", theme="R&D")
  ```

- 📦 **Architecture modulaire** : ajoutez un extracteur ou un moteur en quelques lignes.  
- 🐳 **Docker-ready** & **CI-friendly** (tests PyTest, docs MkDocs).

---

## Arborescence du dépôt

```text
.
├── doc_loader/   # Extraction & chargement
├── vectordb/     # Modèles SQLAlchemy + recherche
├── pipeline/     # Orchestrateur end-to-end
├── docs/              # Documentation MkDocs
├── demo/              # Fichiers d’exemple
├── start.sh           # Script de démarrage API
├── Dockerfile         # Build image
└── ...
```

---

## Installation

### Prérequis

* Python ≥ 3.11  
* PostgreSQL ≥ 14 avec l’extension **pgvector**  
* (Optionnel) WSL 2 + openSUSE Tumbleweed

### Étapes

```bash
# 1. Cloner
git clone https://github.com/<your-gh-user>/clea-api.git
cd clea-api

# 2. Dépendances
uv pip install -r requirements.txt   # ↳ gestionnaire 'uv'

# 3. Variables d’environnement
cp .env.sample .env   # puis éditez au besoin

# 4. Initialisation DB
uv python -m clea_vectordb.init_db

# 5. Lancer l’API
./start.sh            # ➜ http://localhost:8080
```

---

## Utilisation express

### Chargement simple

```bash
curl -X POST http://localhost:8080/doc_loader/upload-file \
     -F "file=@demo/devis.pdf" -F "theme=Achat"
```

### Pipeline complet (upload → segment → index)

```bash
curl -X POST http://localhost:8080/pipeline/process-and-store \
     -F "file=@demo/devis.pdf" -F "theme=Achat" -F "max_length=800"
```

### Recherche hybride

```bash
curl -X POST http://localhost:8080/search/hybrid_search \
     -H "Content-Type: application/json" \
     -d '{"query":"analyse risques", "top_k":8}'
```

---

## Tests

```bash
uv run pytest           # tous les tests unitaires
```

---

## Déploiement Docker

```bash
docker build -t clea-api .
docker run -p 8080:8080 clea-api
```

---

## Contribuer 🤝

1. **Fork** → branche (`feat/ma-feature`)  
2. `uv run pytest && mkdocs build` doivent passer  
3. Ouvrez une **Pull Request** claire et concise

---

## Licence

Distribué sous licence **MIT** – voir [`LICENSE`](LICENSE).
