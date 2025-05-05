# Technologie de stockage Clea-API

Ce document présente l'architecture et les choix technologiques de la base de données utilisée par **Clea-API**.  
La solution repose sur **PostgreSQL** enrichi de l'extension **pgvector**, piloté via **SQLAlchemy**.

---

## Table des matières

1. Configuration et connexion
2. Modèles de données
   - Document
   - Chunk
   - IndexConfig
3. Indexation vectorielle
4. Schéma global
5. Bonnes pratiques
6. Installation et configuration

---

## 1. Configuration et connexion

Les paramètres de connexion sont lus depuis le fichier .env :

```python
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "vectordb")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
```

### Composants principaux

* **Engine SQLAlchemy** : `create_engine(DATABASE_URL)`
* **Session factory** : `SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)`
* **Base déclarative** : `Base = declarative_base()`

### Utilitaire de session

```python
def get_db():
    """Crée et retourne une session de base de données.
    
    Génère une session SQLAlchemy compatible avec FastAPI à utiliser 
    comme dépendance dans les endpoints.
    
    Yields:
        Session: Session SQLAlchemy pour les opérations de base de données
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Initialisation

```python
def init_db():
    """Initialise la base de données avec les tables et extensions nécessaires.
    
    Crée l'extension pgvector si elle n'existe pas déjà et génère toutes 
    les tables définies dans les modèles SQLAlchemy.
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
```

---

## 2. Modèles de données

### 2.1. Document

```python
class Document(Base):
    """Stocke les métadonnées globales des documents.
    
    Attrs:
        id (int): Identifiant unique du document
        title (str): Titre du document
        theme (str): Thème ou catégorie du document
        document_type (str): Type de document (PDF, DOCX, etc.)
        publish_date (Date): Date de publication du document
        corpus_id (str): UUID du corpus auquel appartient ce document
        created_at (Date): Date d'ajout à la base de données
        index_needed (bool): Indique si une mise à jour d'index est nécessaire
        chunks (relationship): Relation avec les fragments textuels
    """
    __tablename__ = "documents"

    id            = mapped_column(Integer, primary_key=True)
    title         = mapped_column(String(255), nullable=False)
    theme         = mapped_column(String(100))
    document_type = mapped_column(String(100))
    publish_date  = mapped_column(Date)
    corpus_id     = mapped_column(String(36), index=True)
    created_at    = mapped_column(Date, default=datetime.now)
    index_needed  = mapped_column(Boolean, default=False)

    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_document_theme", "theme"),
        Index("idx_document_type", "document_type"),
        Index("idx_document_date", "publish_date"),
        Index("idx_document_corpus", "corpus_id"),
    )
```

* **Métadonnées** : titre, thème, type, date de publication, identifiant de corpus (UUID)
* **Relation 1–N** vers les `Chunk` (cascade delete)
* **Index SQL** sur les colonnes fréquemment utilisées pour le filtrage

---

### 2.2. Chunk

```python
class Chunk(Base):
    """Stocke les fragments de texte avec leurs embeddings vectoriels.
    
    Attrs:
        id (int): Identifiant unique du fragment
        document_id (int): Référence au document parent
        content (str): Texte du fragment
        embedding (Vector): Représentation vectorielle (768 dim)
        start_char (int): Position de début dans le document source
        end_char (int): Position de fin dans le document source
        hierarchy_level (int): Niveau hiérarchique (0-3)
        parent_chunk_id (int): Référence au fragment parent
        document (relationship): Relation avec le document parent
        parent (relationship): Relation avec le fragment parent
        children (relationship): Relation avec les fragments enfants
    """
    __tablename__ = "chunks"

    id             = mapped_column(Integer, primary_key=True)
    document_id    = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content        = mapped_column(Text, nullable=False)
    embedding      = mapped_column(Vector(768))
    start_char     = mapped_column(Integer)
    end_char       = mapped_column(Integer)
    hierarchy_level= mapped_column(Integer, default=3)
    parent_chunk_id= mapped_column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"))

    document = relationship("Document", back_populates="chunks")
    parent   = relationship("Chunk", remote_side=[id], back_populates="children")
    children = relationship("Chunk", back_populates="parent", cascade="all, delete-orphan", single_parent=True)

    __table_args__ = (
        Index("idx_chunk_document_level", "document_id", "hierarchy_level"),
        Index("idx_chunk_parent", "parent_chunk_id"),
    )
```

* **Contenu texte** segmenté en **chunks** hiérarchiques (niveau 0 à 3)
* **Embedding** : vecteur de dimension 768 stocké via **pgvector**
* **Auto-relation** parent–enfant pour reconstruire l'arborescence textuelle
* **Index** pour accélérer les recherches par document et niveau hiérarchique

#### Hiérarchie des chunks

| Niveau | Description | Usage |
|--------|-------------|-------|
| 0 | Document entier | Aperçu global |
| 1 | Sections | Structure principale |
| 2 | Paragraphes | Contexte intermédiaire |
| 3 | Fragments | Recherche précise |

---

### 2.3. IndexConfig

```python
class IndexConfig(Base):
    """Configure les index vectoriels par corpus.
    
    Attrs:
        id (int): Identifiant unique de la configuration
        corpus_id (str): Identifiant du corpus concerné
        index_type (str): Type d'index vectoriel ('ivfflat' ou 'hnsw')
        is_indexed (bool): Indique si l'index a été créé
        chunk_count (int): Nombre de fragments dans le corpus
        last_indexed (Date): Dernière date d'indexation
        ivf_lists (int): Nombre de listes pour index IVFFLAT
        hnsw_m (int): Nombre de connexions par nœud pour HNSW
        hnsw_ef_construction (int): Facteur d'exploration pour HNSW
    """
    __tablename__ = "index_configs"

    id                = mapped_column(Integer, primary_key=True)
    corpus_id         = mapped_column(String(36), unique=True, nullable=False)
    index_type        = mapped_column(String(20), default="ivfflat")
    is_indexed        = mapped_column(Boolean, default=False)
    chunk_count       = mapped_column(Integer, default=0)
    last_indexed      = mapped_column(Date, nullable=True)
    ivf_lists         = mapped_column(Integer, default=100)
    hnsw_m            = mapped_column(Integer, default=16)
    hnsw_ef_construction = mapped_column(Integer, default=200)
```

* **Configuration vectorielle** par `corpus_id`
* **Types d'index** disponibles :
  * `ivfflat` (inverted file) - rapide pour corpus moyens, moins précis
  * `hnsw` (graph-based) - plus précis, meilleur pour grands corpus
* Paramètres ajustables pour optimiser vitesse et précision de recherche

---

## 3. Indexation vectorielle

### Principes de base

* **Extension pgvector** : intégrée à PostgreSQL via `CREATE EXTENSION vector`
* **Stockage** : embeddings conservés dans des colonnes de type `Vector(dimension)`
* **Index dynamiques** : création SQL à la demande selon la typologie du corpus

### Types d'index disponibles

#### IVFFLAT (Inverted File with Flat Compression)

```sql
CREATE INDEX idx_ivfflat ON chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100)
WHERE document_id IN (SELECT id FROM documents WHERE corpus_id = 'corpus_xyz')
```

* **Avantages** : Rapide à construire, efficace pour des volumes moyens (< 300K chunks)
* **Paramétrage** : `lists` (nombre de clusters) - plus élevé = plus précis mais plus lent

#### HNSW (Hierarchical Navigable Small World)

```sql
CREATE INDEX idx_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200)
WHERE document_id IN (SELECT id FROM documents WHERE corpus_id = 'corpus_xyz')
```

* **Avantages** : Plus précis, excellentes performances même avec des millions de vecteurs
* **Paramétrage** : 
  * `m` (connexions par nœud) - équilibre entre vitesse et précision
  * `ef_construction` (facteur d'exploration) - plus élevé = plus précis mais plus lent à construire

---

## 4. Schéma global

```
╔═════════════╗
║  Document   ║
║ (métadonnées)══════╗
╚═════════════╝      ║
       │             ║ 1:N
       │ 1:N         ║
       ▼             ▼
╔═════════════╗    ╔═════════════╗
║    Chunk    ║    ║    Chunk    ║
║ Niveau 0-2  ║◄───║  Niveau 3   ║
║ (sections)  ║    ║  (détails)  ║
╚═════════════╝    ╚═════════════╝
       │
       │ 
       ▼
╔═════════════╗
║ IndexConfig ║
║ (par corpus)║
╚═════════════╝
```

* **Document** : contient uniquement les métadonnées
* **Chunks** : stockent le contenu textuel hiérarchique et les embeddings
* **IndexConfig** : paramétrage des index vectoriels par corpus

---

## 5. Bonnes pratiques

### Performances

* **Évitez les transactions longues** avec des embeddings : consomment beaucoup de mémoire
* **Créez des index par corpus** plutôt qu'un seul global
* **Ajustez les paramètres** selon votre volume :
  * Petits corpus (< 50K chunks) : IVFFLAT avec 50-100 listes
  * Corpus moyens (50K-300K) : IVFFLAT avec 100-300 listes
  * Grands corpus (> 300K) : HNSW avec m=16, ef_construction=200

### Monitoring

* Surveillez `last_indexed` et `chunk_count` pour détecter les dérives de performance
* Reconstruisez les index si la recherche se dégrade (`VACUUM ANALYZE chunks`)

### Sécurité

* Limitez les dimensions des vecteurs (768 ici) pour éviter la surcharge mémoire
* Utilisez des corpus_id en UUID pour l'isolation et la sécurité

---

## 6. Installation et configuration

### Prérequis

* PostgreSQL ≥ 14
* Extension pgvector installée
* Python ≥ 3.11

### Installation sur openSUSE Tumbleweed (WSL)

```bash
# Installer PostgreSQL et les dépendances
sudo zypper install postgresql14 postgresql14-server postgresql14-devel git gcc

# Installer pgvector depuis les sources
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Initialiser la base de données PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo -u postgres createuser -s $USER
createdb vectordb

# Configurer le projet Python
cd /chemin/vers/clea-api
uv pip install -r requirements.txt

# Initialiser la base de données
uv python -m vectordb.src.database
```

### Configuration minimale du fichier .env

```

DB_USER=votre_utilisateur
DB_PASSWORD=votre_mot_de_passe
DB_HOST=localhost
DB_PORT=5432
DB_NAME=vectordb
```

---

> Source : database.py  
> Dernière mise à jour : **03 mai 2025**
