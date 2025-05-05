# Point d'entrée principal : `main.py`

Le fichier **`main.py`** constitue le **démarreur** de tout le framework **Cléa-API**, initialisant l'environnement, la base de données, les extensions, puis lançant l'application FastAPI via Uvicorn.

---

## 1. Chargement de la configuration

- Charge les variables d'environnement depuis `.env` (via `python-dotenv`)  
- Configure le **logger** global  
- Lit les paramètres PostgreSQL et API (hôte, port, workers, niveau de log) :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}

```python
load_dotenv()
POSTGRES_USER     = os.getenv("DB_USER")
POSTGRES_PASSWORD = os.getenv("DB_PASSWORD")
…
API_HOST  = os.getenv("API_HOST", "localhost")
API_PORT  = int(os.getenv("API_PORT", 8080))
API_WORKERS = int(os.getenv("API_WORKERS", 1))
API_LOG_LEVEL = os.getenv("API_LOG_LEVEL", "info")
````

---

## 2. Gestion centralisée du logging

### `configure_logging(debug_mode: bool = False) → None`

Configure le système de journalisation pour toute l'application:

1. Définit le niveau de log en fonction du mode debug (`DEBUG` ou `INFO`)
2. Configure le logger racine avec un format standardisé:

```python
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

3. Ajuste la verbosité des loggers tiers (uvicorn, sqlalchemy) pour réduire le bruit

Ce système permet d'utiliser dans tous les modules:

```python
from utils import get_logger

# Obtenir un logger préfixé automatiquement
logger = get_logger("mon_module.sous_module")

# Utiliser selon le contexte
logger.debug("Détail technique") # Visible uniquement en mode debug
logger.info("Information importante") # Visible en mode normal
logger.error("Problème critique") # Toujours visible
```

La centralisation évite de redéfinir le niveau dans chaque module.

---

## 3. Arguments en ligne de commande

L'application accepte plusieurs arguments pour personnaliser son lancement:

| Argument | Description | Défaut |
|----------|-------------|--------|
| `--debug` | Active les logs détaillés | `False` |
| `--port` | Port d'écoute du serveur | Valeur de .env ou `8080` |
| `--host` | Hôte d'écoute du serveur | Valeur de .env ou `localhost` |
| `--workers` | Nombre de processus workers | Valeur de .env ou `1` |

Exemple d'utilisation:

```bash
python main.py --debug --port 9000 --workers 4
```

---

## 4. Vérification et démarrage de PostgreSQL

### `start_postgres() → bool`

1. Récupère l'utilisateur courant (`get_current_user`).
2. Vérifie la disponibilité de PostgreSQL (`check_postgres_status`).
3. Si indisponible, affiche des **suggestions d'installation** pour Linux, notamment OpenSUSE Tumbleweed.
4. Retourne `True` si PostgreSQL est accessible, `False` sinon.&#x20;

---

## 5. Initialisation de la base de données

### `setup_database() → bool`

1. Crée les tables SQLAlchemy (`Base.metadata.create_all`) et l'extension **vector**.
2. Appelle `init_db()` pour installer pgvector et valider la création des tables.
3. Renvoie `True` si l'extension et les tables sont correctement créées.&#x20;

---

## 6. Cycle de vie de l'application

### `lifespan(app: FastAPI) → AsyncGenerator[None, None]`

Gestionnaire **asynchrone** exécuté au démarrage et à l'arrêt :

* **Au démarrage** :

  1. Démarre/vérifie PostgreSQL via `start_postgres`.
  2. Vérifie l'existence des tables (`verify_database_tables`), et lance `setup_database` si nécessaire.
* **À l'arrêt** :

  * Vide le cache de ressources globales.&#x20;

---

## 7. Création de l'application FastAPI

```python
app = FastAPI(
    title="Cléa API",
    description="API pour gérer les documents et effectuer des recherches sémantiques.",
    version="0.1.1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
```

* Active **Swagger UI** (docs) et **ReDoc** (`/redoc`).
* Associe le **lifespan** défini ci-dessus.&#x20;

---

## 8. Middleware et routeurs

* **CORS** : autorise toutes les origines, méthodes et headers (`CORSMiddleware`).
* **Inclusion des routers** :

  * `/database` → crud documents & chunks
  * `/search`   → recherche hybride
  * `/index`    → gestion des index vectoriels
  * doc_loader → upload et extraction de documents
  * pipeline → traitement complet (extract → segment → insert)&#x20;

---

## 9. Gestion des erreurs globales

* **`StarletteHTTPException`** → renvoie `{ "error": detail }`
* **`RequestValidationError`** → renvoie `{ "error": "Invalid request", "details": [...] }`
* **`Exception`** → capture toute erreur non gérée et renvoie `500 Internal server error`.&#x20;

---

## 10. Endpoints de santé

```python
@app.get("/")
async def root():
    return {"message": "Cléa API is running"}
```

– Vérifie simplement que l'API est en ligne.&#x20;

---

## 11. Lancement du serveur

Lorsque main.py est exécuté directement (`if __name__ == "__main__"`), il :

1. Parse les arguments en ligne de commande (debug, host, port, workers)
2. Configure le logging via `configure_logging()`
3. Crée une configuration **Uvicorn** optimisée (reload, workers, proxy headers, choix auto de loop/http)
4. Démarre le serveur avec `uvicorn.Server(config).run()`.&#x20;

```bash
python main.py
# ou avec options
python main.py --debug --port 9000
# ou via uvicorn directement
uvicorn main:app --host $API_HOST --port $API_PORT --workers $API_WORKERS
```

---

> **Fichier source** : main.py&#x20;
> **Dernière mise à jour** : 04 mai 2025
