import os

from datetime import datetime


from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    create_engine,
    text,
    inspect,
)

from sqlalchemy.orm import (
    declarative_base,
    mapped_column,
    relationship,
    sessionmaker,
)

from utils import get_logger
# ---------------------------------------------------------------------------

load_dotenv()

# Configuration de la base de données
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "vectordb")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# --------------------------------------------------------------------------- #
#  Configuration du logger
# --------------------------------------------------------------------------- #
logger = get_logger("vectordb.database")


# Création du moteur SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Document(Base):
    """Modèle SQLAlchemy pour la table des documents.

    Stocke les métadonnées globales des documents sans leur contenu.

    Attributes:
        id: Identifiant unique du document.
        title: Titre du document.
        theme: Thème ou catégorie du document.
        document_type: Type de document (PDF, DOCX, etc.).
        publish_date: Date de publication du document.
        corpus_id: UUID du corpus auquel appartient ce document.
        created_at: Date de création dans la base de données.
        index_needed: Indique si une mise à jour d'index est nécessaire pour ce document.
        chunks: Relation avec les fragments textuels du document.
    """

    __tablename__ = "documents"

    id = mapped_column(Integer, primary_key=True)
    title = mapped_column(String(255), nullable=False)
    theme = mapped_column(String(100))
    document_type = mapped_column(String(100))
    publish_date = mapped_column(Date)
    corpus_id = mapped_column(
        String(36), index=True
    )  # UUID stocké sous forme de chaîne
    created_at = mapped_column(Date, default=datetime.now)
    index_needed = mapped_column(Boolean, default=False)

    # Relation avec les chunks
    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    # Index sur les colonnes fréquemment utilisées pour le filtrage
    __table_args__ = (
        Index("idx_document_theme", "theme"),
        Index("idx_document_type", "document_type"),
        Index("idx_document_date", "publish_date"),
        Index("idx_document_corpus", "corpus_id"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = mapped_column(Integer, primary_key=True)
    document_id = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(768))
    start_char = mapped_column(Integer)
    end_char = mapped_column(Integer)
    hierarchy_level = mapped_column(Integer, default=3)
    parent_chunk_id = mapped_column(
        Integer, ForeignKey("chunks.id", ondelete="CASCADE")
    )

    # relations ----------------------------------------------------------------
    document = relationship("Document", back_populates="chunks")

    parent = relationship(  # 1 parent  ←  N children
        "Chunk",
        remote_side=[id],
        back_populates="children",
    )
    children = relationship(
        "Chunk",
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True,  #  ✅ indispensable !
    )

    __table_args__ = (
        Index("idx_chunk_document_level", "document_id", "hierarchy_level"),
        Index("idx_chunk_parent", "parent_chunk_id"),
    )


# Configuration pour basculer entre différents types d'index
class IndexConfig(Base):
    """Modèle SQLAlchemy pour la configuration des index.

    Stocke les paramètres de configuration pour les index vectoriels par corpus.
    """

    __tablename__ = "index_configs"

    id = mapped_column(Integer, primary_key=True)
    corpus_id = mapped_column(String(36), unique=True, nullable=False)
    index_type = mapped_column(String(20), default="ivfflat")  # 'ivfflat' ou 'hnsw'
    is_indexed = mapped_column(Boolean, default=False)
    chunk_count = mapped_column(Integer, default=0)
    last_indexed = mapped_column(Date, nullable=True)

    # Configuration spécifique aux index
    ivf_lists = mapped_column(Integer, default=100)
    hnsw_m = mapped_column(Integer, default=16)
    hnsw_ef_construction = mapped_column(Integer, default=200)

class SearchQuery(Base):
    """Modèle pour l'historisation des recherches effectuées.
    
    Cette table stocke l'historique des requêtes de recherche avec des métadonnées
    contextuelles pour permettre l'analyse statistique des tendances et usages.
    
    Attributes:
        id: Identifiant unique de la recherche.
        query_text: Texte de la requête effectuée.
        theme: Thème optionnel sur lequel la recherche a été restreinte.
        document_type: Type de document optionnel sur lequel la recherche a été restreinte.
        corpus_id: Identifiant du corpus optionnel sur lequel la recherche a été restreinte.
        results_count: Nombre de résultats retournés.
        confidence_level: Niveau de confiance calculé pour les résultats.
        created_at: Date et heure d'exécution de la recherche.
        user_id: Identifiant optionnel de l'utilisateur ayant effectué la recherche.
    """
    __tablename__ = "search_queries"
    
    id = mapped_column(Integer, primary_key=True)
    query_text = mapped_column(String, nullable=False)
    theme = mapped_column(String, nullable=True)
    document_type = mapped_column(String, nullable=True)
    corpus_id = mapped_column(String, nullable=True)
    results_count = mapped_column(Integer, default=0)
    confidence_level = mapped_column(Float, default=0.0)
    created_at = mapped_column(DateTime, default=datetime.now)
    user_id = mapped_column(String, nullable=True)
    
# Fonction pour obtenir une session de base de données
def get_db():
    """Crée et retourne une session de base de données.

    Yields:
        Session: Session SQLAlchemy à utiliser pour les opérations de base de données.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Fonction pour initialiser la base de données
def init_db():
    """Initialise la base de données avec les tables et extensions nécessaires.

    Crée l'extension pgvector et les tables définies dans les modèles SQLAlchemy.
    """
    # Créer l'extension pgvector si elle n'existe pas déjà
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Créer les tables
    Base.metadata.create_all(bind=engine)
    print("Base de données initialisée avec succès.")


##############################################################
#  Fonction helper
##############################################################

def update_db():
    """Met à jour le schéma de la base de données pour refléter les modèles SQLAlchemy actuels.
    
    Cette fonction crée les tables manquantes et adapte les tables existantes aux nouveaux schémas.
    Elle est à utiliser après ajout de nouveaux modèles ou modifications de modèles existants.
    
    Note:
        L'extension pgvector doit déjà être installée.
    
    Returns:
        Dict[str, Any]: Résultat des opérations de mise à jour.
    """   
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    
    # Récupération des tables existantes
    existing_tables = inspector.get_table_names()
    
    # Tables à créer basées sur les modèles définis
    tables_to_create = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            tables_to_create.append(table_name)
    
    # Créer seulement les tables manquantes
    if tables_to_create:
        Base.metadata.create_all(bind=engine, tables=[
            Base.metadata.tables[table_name] for table_name in tables_to_create
        ])
        print(f"Tables créées : {', '.join(tables_to_create)}")
    else:
        print("Aucune nouvelle table à créer.")
    
    return {
        "success": True,
        "created_tables": tables_to_create,
        "existing_tables": existing_tables
    }


# Point d'entrée pour l'exécution en ligne de commande
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "update_db":
        print("Mise à jour du schéma de la base de données...")
        result = update_db()
        print(f"Mise à jour terminée. Tables créées : {result['created_tables']}")
        print(f"Tables existantes : {result['existing_tables']}")
    elif len(sys.argv) > 1 and sys.argv[1] == "init_db":
        print("Initialisation de la base de données...")
        init_db()
        print("Base de données initialisée avec succès.")
    else:
        print("Utilisation: python -m vectordb.src.database [update_db|init_db]")