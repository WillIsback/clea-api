# Cléa-API 🚀  

*Hybrid document-search framework for PostgreSQL + pgvector*

[![Licence MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-ReadTheDocs-green.svg)](https://WillIsback.github.io/clea-api)

Cléa-API charge des documents multi-formats, les segmente, les vectorise et
fournit une **recherche hybride (vectorielle + filtres SQL)** prête à l'emploi.
Il s'utilise :

* via **endpoints REST** (FastAPI) ;
* en **librairie Python** (extraction, pipeline, recherche) ;
* avec une **base PostgreSQL + pgvector** auto-indexée par corpus ;
* **100% local et hors-ligne** pour vos données sensibles.

---

## Sommaire rapide

| Sujet | Documentation |
|-------|---------------|
| **Chargement & extraction** | [Extracteurs](docs/lib/doc_loader/extractor_lib.md) · [Segmentation](docs/lib/doc_loader/splitter_lib.md) |
| **Base de données & index vectoriels** | [Database](docs/database.md) |
| **Moteur de recherche hybride** | [Search](docs/lib/vectordb/search_lib.md) |
| **Pipeline end-to-end** | [Pipeline](docs/lib/pipeline/pipeline_lib.md) |
| **Référence API Python (autogen)** | [Doc Loader](docs/api/lib/doc_loader/extractor_references.md) · [Vectordb](docs/api/lib/vectordb/crud_references.md) · [Pipeline](docs/api/lib/pipeline/pipeline_references.md) |
| **IA génératrice (RAG)** | [AskAI](docs/lib/askai/rag_lib.md) |
| **Stats** | [Stats](docs/lib/stats/stats_computer_lib.md) |
| **OpenAPI / Endpoints REST** | [REST API](docs/api/rest/rest_api.md) |

---

## Caractéristiques clés

- 🔒 **100% local & hors-ligne** : traitement sécurisé pour données confidentielles
- 🔄 **Chargement multi-formats** : PDF, DOCX, HTML, JSON, TXT, …  
- 🧩 **Segmentation hiérarchique** : Section ▶ Paragraphe ▶ Chunk  
- 🔍 **Recherche hybride** : *ivfflat* ou *HNSW* + Cross-Encoder rerank  
- 🤖 **RAG avec petits LLMs** : génération augmentée via modèles Qwen3 légers
- ⚡ **Pipeline "one-liner"** :  

  ```python
  from pipeline import process_and_store
  from askai.src.rag import RAGProcessor
  
  # Traitement de documents
  process_and_store("rapport.pdf", theme="R&D")
  
  # Interrogation des documents via RAG
  response, context = rag_processor.retrieve_and_generate(
      "Quelles sont les principales recommandations du rapport?"
  )
  ```

- 📦 **Architecture modulaire** : ajoutez un extracteur ou un modèle en quelques lignes  
- 🐳 **Docker-ready** & **CI-friendly** (tests PyTest, docs MkDocs)

---

## Options de lancement

Cléa-API supporte plusieurs modes de lancement avec différentes options de configuration:

```bash
# Mode standard
./start.sh

# Mode développeur avec logs détaillés
uv run main.py --debug

# Configuration avancée
uv run main.py --host 0.0.0.0 --port 9000 --workers 4

# Avec variables d'environnement
API_LOG_LEVEL=debug API_PORT=9000 ./start.sh
```

### Niveaux de journalisation

Le système de logs est centralisé et configurable:

| Mode | Description | Commande |
|------|-------------|----------|
| INFO (défaut) | Informations essentielles | `uv run main.py` |
| DEBUG | Détails techniques | `uv run main.py --debug` |
| WARN/ERROR | Uniquement alertes et erreurs | `API_LOG_LEVEL=warning uv run main.py` |

Les logs suivent le format standard:

```log
2025-05-04 16:30:21,483 - clea-api.doc_loader - INFO - Document chargé: demo.pdf (3.2MB)
```

---

## Arborescence du dépôt

```text
.
├── doc_loader/   # Extraction & chargement de documents
├── vectordb/     # Modèles SQLAlchemy + recherche 
├── pipeline/     # Orchestrateur end-to-end
├── askai/        # Génération RAG avec modèles légers
├── docs/         # Documentation MkDocs
├── demo/         # Fichiers d'exemple
├── start.sh      # Script de démarrage API
├── Dockerfile    # Build image
└── ...
```

---

## Installation

### Prérequis

* Python ≥ 3.11  
* PostgreSQL ≥ 14 avec l'extension **pgvector**  
* (Recommandé) WSL 2 + openSUSE Tumbleweed

### Installation sur openSUSE Tumbleweed

```bash
# 1. Installer les dépendances système
sudo zypper install postgresql15 postgresql15-server postgresql15-devel python311 python311-devel gcc

# 2. Activer PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 3. Installer uv (gestionnaire de paquets Python moderne)
curl -sSf https://astral.sh/uv/install.sh | sh
```

### Installation de Cléa-API

```bash
# 1. Cloner
git clone https://github.com/<your-gh-user>/clea-api.git
cd clea-api

# 2. Dépendances (avec uv)
uv pip install -r requirements.txt

# 3. Pour le module askai (optionnel)
uv pip install -r askai/requirements_askai.txt

# 4. Variables d'environnement
cp .env.sample .env   # puis éditez au besoin

# 5. Initialisation DB et extension pgvector
uv python -m vectordb.src.database init_db

# 6. Lancer l'API
uv run main.py           # ➜ http://localhost:8080
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

### Génération RAG (AskAI)

```bash
curl -X POST http://localhost:8080/askai/query \
     -H "Content-Type: application/json" \
     -d '{
       "question": "Résumer les points importants du document", 
       "theme": "Achat", 
       "enable_thinking": true
     }'
```

### Utilisation en mode streaming

```bash
curl -N -X POST http://localhost:8080/askai/query_stream \
     -H "Content-Type: application/json" \
     -d '{"question": "Expliquer la structure du document"}'
```

---

## Sécurité et confidentialité

Cléa-API est conçu pour traiter des données **sensibles et confidentielles** avec une approche orientée sécurité:

- **100% hors-ligne**: aucune donnée n'est envoyée vers des services externes
- **Modèles légers locaux**: tous les LLMs sont exécutés localement (Qwen3-0.6B/1.7B)
- **Aucune télémétrie**: pas de tracking ni d'analytics 
- **Aucune dépendance cloud**: fonctionne en environnement air-gapped

Cette approche est idéale pour les organisations avec des contraintes strictes de confidentialité (données médicales, financières, juridiques, etc.).

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

Distribué sous licence **MIT** – voir LICENSE.