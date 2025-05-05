# Cléa-API

*Framework* de **chargement de documents**, **recherche hybride** et **RAG** (vectorielle + métadonnées + génération) pour PostgreSQL + pgvector.  
Conçu **100 % local & hors-ligne** pour vos données sensibles (médicales, financières, juridiques…). 

[![Licence MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/WillIsback/clea-api/blob/main/LICENSE)  

---

## Accès rapides 📚

| Sujet                                       | Documentation                                              |
|---------------------------------------------|------------------------------------------------------------|
| **Chargement & extraction**                 | [Extracteurs](lib/doc_loader/extractor_lib.md) · [Segmentation](lib/doc_loader/splitter_lib.md) |
| **Base de données & index vectoriels**      | [Database](database.md)                                     |
| **Moteur de recherche hybride**             | [Search](lib/vectordb/search_lib.md)                        |
| **Pipeline end-to-end**                     | [Pipeline](lib/pipeline/pipeline_lib.md)                    |
| **IA générative & RAG (AskAI)**             | [AskAI](lib/askai/rag_lib.md)                               |
| **Référence API Python (autogen)**          | [Doc Loader](api/lib/doc_loader/extractor_references.md) · [Vectordb](api/lib/vectordb/crud_references.md) · [Pipeline](api/lib/pipeline/pipeline_references.md) |
| **OpenAPI / Endpoints REST**                | [REST API](api/rest/rest_api.md)                            |

---

## Caractéristiques principales

- 🔒 **100 % local & hors-ligne** : aucun appel à des services externes, parfait pour les données confidentielles  
- 📂 **Chargement multi-formats** : PDF, DOCX, HTML, JSON, TXT…  
- 🧩 **Segmentation hiérarchique** : Section → Paragraphe → Chunk  
- 🔍 **Recherche hybride** : *ivfflat* ou *HNSW* + filtres SQL + re-ranking Cross-Encoder  
- 🤖 **RAG avec petits LLMs (AskAI)** : génération augmentée en local (Qwen3-0.6B/1.7B)  
- ⚡ **Pipeline "one-liner"** :  

```python
  from pipeline import process_and_store
  process_and_store("report.pdf", theme="R&D")
```

* 🛠️ **Extensible** : ajoutez un extracteur ou un modèle en quelques lignes
* 🐳 **Docker-ready** & **CI-friendly** (tests PyTest, MkDocs)&#x20;

---

## Structure du dépôt

```text
.
├── doc_loader/   # Extraction & chargement
├── vectordb/     # Modèles & recherche
├── pipeline/     # Orchestration end-to-end
├── askai/        # RAG & génération locale
├── docs/         # Documentation MkDocs ← vous êtes ici
├── demo/         # Exemples de fichiers
└── main.py       # Démarreur FastAPI + configuration
```

---

## Installation rapide

```bash
git clone https://github.com/votre-repo/clea-api.git
cd clea-api

# Dépendances Python
uv pip install -r requirements.txt
uv pip install -r askai/requirements_askai.txt   # pour AskAI

# Variables d’environnement
cp .env.sample .env
# (éditez DB_USER, DB_PASSWORD, etc.)

# Initialiser la DB + extension pgvector
uv python -m vectordb.src.database init_db

# Lancer l’API
./start.sh   # ou uv run main.py
```

L’API sera disponible sur [http://localhost:8080](http://localhost:8080).

---

> Conçu pour un usage **local** et **sécurisé**, sans fuite de données vers le cloud.
> Voir le [README principal](../README.md) pour plus de détails.
