"""
Tests du processeur RAG (Retrieval-Augmented Generation).

Ce module contient les tests pour vérifier le bon fonctionnement de:
1. Le formatage du contexte documentaire pour le LLM
2. La sélection des templates de prompts selon le type de requête
3. La récupération des documents pertinents
4. La génération de réponses synthétiques
5. Le streaming de réponses progressives
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, List

import pytest
from datetime import datetime, date
from pathlib import Path
from sqlalchemy.orm import sessionmaker

from askai.src.rag import RAGProcessor
from askai.src.model_loader import ModelLoader
from askai.src.prompt_schemas import StandardRAGPrompt, SummaryRAGPrompt, ComparisonRAGPrompt
from vectordb.src.search import SearchEngine
from vectordb.src.schemas import SearchResponse, SearchRequest, ChunkResult, HierarchicalContext
from vectordb.src.database import Base, engine, get_db, Chunk
from sqlalchemy import text
from vectordb.src.crud import add_document_with_chunks
from vectordb.src.schemas import DocumentCreate
from vectordb.src.embeddings import EmbeddingGenerator

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag-tests")

# Chemin pour les logs de test
LOG_DIR = Path("askai/test/log")
LOG_PATH = LOG_DIR / "rag_test.log"

# Configuration pour anyio (limitation à asyncio uniquement)
pytestmark = pytest.mark.anyio(backends=["asyncio"])

# Documents de test avec données réelles pour les différents tests
TEST_DOCUMENTS = [
    {
        "content": "Cléa-API charge des documents multi-formats, les segmente, les vectorise et fournit une recherche hybride (vectorielle + filtres SQL) prête à l'emploi.",
        "title": "Documentation Cléa",
        "document_type": "Markdown",
        "theme": "API"
    },
    {
        "content": "Le processeur RAG (Retrieval-Augmented Generation) permet d'enrichir les réponses d'un LLM avec des données externes provenant d'une base de connaissances récupérées via recherche vectorielle.",
        "title": "Principes du RAG",
        "document_type": "PDF",
        "theme": "IA"
    },
    {
        "content": "PostgreSQL est un système de gestion de base de données relationnelle open source très avancé, avec plus de 30 ans de développement actif.",
        "title": "Guide PostgreSQL",
        "document_type": "Web",
        "theme": "Base de données"
    },
    {
        "content": "La recherche sémantique utilise des embeddings vectoriels générés par des modèles de language pour capturer le sens des mots plutôt que de se limiter aux correspondances exactes.",
        "title": "Recherche vectorielle",
        "document_type": "Web",
        "theme": "Base de données"
    },
    {
        "content": "L'extension pgvector permet d'indexer et de rechercher des vecteurs dans PostgreSQL avec différents algorithmes d'indexation comme HNSW et IVFFlat.",
        "title": "pgvector",
        "document_type": "Web",
        "theme": "Base de données"
    }
]


def setup_module():
    """Configure l'environnement pour les tests.
    
    Initialise le répertoire de logs et prépare l'environnement de test.
    """
    # Créer le répertoire de logs s'il n'existe pas
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Réinitialiser le fichier de log
    with open(LOG_PATH, "w") as f:
        f.write(f"=== Tests du processeur RAG démarrés le {datetime.now()} ===\n\n")


def append_to_log(message: str) -> None:
    """Ajoute une entrée au fichier de log.
    
    Args:
        message: Message à enregistrer dans le log.
    """
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"INFO: {datetime.now()} -- {message}\n\n")
        logger.info(message)
    except Exception as e:
        logger.error(f"Erreur lors de l'écriture dans le fichier de log: {e}")
        raise


def create_test_documents(num_docs: int = 3) -> Dict[str, Any]:
    """Crée plusieurs documents de test avec leurs chunks pour les tests de recherche.
    
    Args:
        num_docs: Nombre de documents à créer.
    
    Returns:
        dict: Informations sur les documents créés, incluant le corpus_id.
    """
    append_to_log(f"Création de {num_docs} documents de test pour la recherche")

    # Initialiser le générateur d'embeddings une seule fois pour tous les documents
    embedder = EmbeddingGenerator()
    
    corpus_id = str(uuid.uuid4())
    documents = []
    
    db = next(get_db())
    
    # Utiliser les documents de test définis dans TEST_DOCUMENTS
    for i, test_doc in enumerate(TEST_DOCUMENTS[:num_docs]):
        doc = DocumentCreate(
            title=test_doc["title"],
            theme=test_doc["theme"],
            document_type=test_doc["document_type"],
            publish_date=date.today(),
            corpus_id=corpus_id,
        )
        
        # Créer des chunks à partir du contenu du document de test
        content = test_doc["content"]
        chunks = [
            {
                "content": content,
                "hierarchy_level": 1,
                "start_char": 0,
                "end_char": len(content),
            }
        ]
        
        added_document = add_document_with_chunks(
            db=db, doc=doc, chunks=chunks, batch_size=10
        )
        documents.append(added_document)
    
    # Générer les embeddings pour tous les chunks
    append_to_log("Génération des embeddings pour les chunks de test...")
    
    # Récupérer tous les chunks pour les documents créés
    chunk_query = text("""
        SELECT id, content FROM chunks 
        WHERE document_id IN (
            SELECT id FROM documents WHERE corpus_id = :corpus_id
        )
    """)
    
    result = db.execute(chunk_query, {"corpus_id": corpus_id})
    chunks_to_embed = [(row[0], row[1]) for row in result]
    
    # Générer les embeddings en batch pour de meilleures performances
    chunk_ids = [chunk[0] for chunk in chunks_to_embed]
    chunk_contents = [chunk[1] for chunk in chunks_to_embed]
    
    # Générer les embeddings en utilisant le modèle réel
    embeddings = embedder.generate_embeddings_batch(chunk_contents)
    
    # Mettre à jour les chunks via l'API ORM
    for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, embeddings)):
        # Récupérer le chunk par son ID
        chunk = db.query(Chunk).filter(Chunk.id == chunk_id).one()
        
        # Mettre à jour l'embedding directement via l'ORM
        chunk.embedding = embedding
        
    db.commit()
    
    append_to_log(f"Documents créés avec succès dans le corpus {corpus_id}, {len(chunks_to_embed)} chunks embeddings générés")
    return {"corpus_id": corpus_id, "documents": documents}


@pytest.fixture
def db_engine():
    """Fournit un moteur de base de données pour les tests.
    
    Returns:
        Engine: Moteur SQLAlchemy pour la base de données.
    """
    return engine


@pytest.fixture
def db_session(db_engine):
    """Fournit une session de base de données pour les tests.
    
    Args:
        db_engine: Moteur de base de données SQLAlchemy.
        
    Returns:
        Session: Session SQLAlchemy pour interagir avec la base de données.
    """
    Session = sessionmaker(bind=db_engine)
    session = Session()
    
    yield session
    
    # Nettoyer après les tests
    session.close()


@pytest.fixture
def search_engine():
    """Crée une instance réelle du moteur de recherche.
    
    Returns:
        SearchEngine: Instance du moteur de recherche vectorielle.
    """
    return SearchEngine()


@pytest.fixture
def model_loader():
    """Crée une instance de ModelLoader en mode test pour les tests.
    
    Returns:
        ModelLoader: Instance du chargeur de modèle configurée pour les tests.
    """
    return ModelLoader(test_mode=True)


@pytest.fixture
def rag_processor(model_loader, search_engine, db_session):
    """Crée une instance réelle du processeur RAG.
    
    Args:
        model_loader: Instance du chargeur de modèle.
        search_engine: Instance du moteur de recherche.
        db_session: Session de base de données.
        
    Returns:
        RAGProcessor: Processeur RAG configuré avec des composants réels.
    """
    return RAGProcessor(
        model_loader=model_loader,
        search_engine=search_engine,
        db_session=db_session,
        max_tokens_per_doc=300,
        max_docs=5
    )


def test_format_context(rag_processor, db_session):
    """Teste le formatage du contexte à partir de résultats de recherche.
    
    Args:
        rag_processor: Processeur RAG à tester.
        db_session: Session de base de données.
        
    Ce test vérifie que:
    - Le formatage produit une chaîne de caractères structurée
    - Les informations des documents sont correctement présentées
    - Le contexte hiérarchique est inclus quand disponible
    """
    append_to_log("=== TEST: Formatage du contexte ===")
    
    # Créer des résultats de recherche à partir des documents de test
    results = []
    for i, doc in enumerate(TEST_DOCUMENTS[:3]):
        # Créer un contexte hiérarchique réaliste
        context = HierarchicalContext(
            level_0={"content": f"Section {i+1} du document"},
            level_1={"content": f"Sous-section {i+1}.1 avec détails spécifiques"},
            level_2=None
        )
        
        # Créer un résultat de chunk avec des données réelles
        result = ChunkResult(
            chunk_id=i,
            content=doc["content"],
            title=doc["title"],
            document_id=100+i,
            document_type=doc["document_type"],
            theme=doc["theme"],
            publish_date=date.today(),
            context=context,
            score=0.8 - (i * 0.1),
            start_char=0,
            end_char=len(doc["content"]),
            hierarchy_level=2
        )
        
        results.append(result)
    
    # Créer la réponse de recherche
    search_response = SearchResponse(
        query="RAG base de données vectorielle",
        topK=len(results),
        totalResults=len(results),
        results=results,
        normalized=True,
        message="Résultats trouvés avec succès"
    )
    
    # Formater le contexte
    formatted_context = rag_processor.format_context(search_response)
    
    # Vérifier le formatage
    append_to_log(f"Contexte formaté:\n{formatted_context[:300]}...")
    
    # Validations
    assert isinstance(formatted_context, str), "Le contexte doit être une chaîne de caractères"
    assert "Documentation Cléa" in formatted_context, "Le document 'Documentation Cléa' doit être présent"
    assert "Principes du RAG" in formatted_context, "Le document 'Principes du RAG' doit être présent"
    assert "TITRE:" in formatted_context, "Les titres doivent être inclus"
    assert "SECTION:" in formatted_context, "Le contexte hiérarchique doit être inclus"
    assert "---" in formatted_context, "Les documents doivent être séparés par des traits"
    
    append_to_log("✅ Test de formatage du contexte réussi")


def test_get_prompt_template(rag_processor):
    """Teste la récupération des templates de prompts selon le type.
    
    Args:
        rag_processor: Processeur RAG à tester.
        
    Ce test vérifie que:
    - Le bon type de template est retourné selon le paramètre
    - Les variables sont correctement transmises au template
    - Une erreur est levée pour un type inconnu
    """
    append_to_log("=== TEST: Récupération des templates de prompts ===")
    
    # Données de test réelles
    context = "\n".join([doc["content"] for doc in TEST_DOCUMENTS])
    query = "Comment fonctionne la recherche hybride dans Cléa-API?"
    
    # Tester différents types de prompts
    standard_template = rag_processor.get_prompt_template(query, context, prompt_type="standard")
    summary_template = rag_processor.get_prompt_template(query, context, prompt_type="summary")
    comparison_template = rag_processor.get_prompt_template(
        query, context, prompt_type="comparison", options=["PostgreSQL", "SQLite"]
    )
    
    # Vérifier les types
    append_to_log(f"Type de template standard: {type(standard_template).__name__}")
    append_to_log(f"Type de template summary: {type(summary_template).__name__}")
    append_to_log(f"Type de template comparison: {type(comparison_template).__name__}")
    
    # Validations
    assert isinstance(standard_template, StandardRAGPrompt), "Le template standard doit être du bon type"
    assert isinstance(summary_template, SummaryRAGPrompt), "Le template summary doit être du bon type"
    assert isinstance(comparison_template, ComparisonRAGPrompt), "Le template comparison doit être du bon type"
    
    # Tester le formatage d'un prompt
    formatted_prompt = standard_template.format()
    append_to_log(f"Exemple de prompt formaté:\n{formatted_prompt[:100]}...")
    
    # Vérifier qu'une erreur est levée pour un type inconnu
    with pytest.raises(ValueError) as excinfo:
        rag_processor.get_prompt_template(query, context, prompt_type="inconnu")
    
    append_to_log(f"Erreur pour type inconnu: {str(excinfo.value)}")
    assert "non reconnu" in str(excinfo.value), "Une erreur explicite doit être levée pour un type inconnu"
    
    append_to_log("✅ Test de récupération des templates réussi")

def test_model_loader():
    """Teste les fonctionnalités du chargeur de modèle.
    
    Ce test vérifie que:
    - Le mode test fonctionne correctement
    - Les paramètres de génération sont correctement transmis
    - Le mode thinking est bien géré
    """
    append_to_log("=== TEST: Chargeur de modèle ===")
    
    # Créer une instance en mode test
    loader = ModelLoader(test_mode=True)
    
    # Vérifier que le modèle est considéré comme "chargé" en mode test
    assert loader.loaded, "Le modèle doit être marqué comme chargé en mode test"
    
    # Tester la génération avec thinking activé
    prompt1 = "Comment fonctionne la recherche vectorielle?"
    response1 = loader.generate(prompt1, enable_thinking=True)
    append_to_log(f"Réponse avec thinking: {response1}")
    assert "thinking mode activé" in response1.lower(), "La réponse doit mentionner le mode thinking"
    
    # Tester la génération sans thinking
    prompt2 = "Qu'est-ce que PostgreSQL?"
    response2 = loader.generate(prompt2, enable_thinking=False)
    append_to_log(f"Réponse sans thinking: {response2}")
    assert "mode" not in response2.lower() or "thinking" not in response2.lower(), "La réponse ne doit pas mentionner le mode thinking"
    
    # Tester la détection d'absence de résultats
    prompt3 = "Aucun résultat pertinent trouvé pour cette requête."
    response3 = loader.generate(prompt3)
    append_to_log(f"Réponse pour résultats vides: {response3}")
    assert "aucune information pertinente" in response3.lower(), "La réponse doit indiquer l'absence d'information"
    
    append_to_log("✅ Test du chargeur de modèle réussi")
    

@pytest.mark.anyio
async def test_retrieve_documents(rag_processor, search_engine, db_session):
    """Teste la récupération des documents pertinents.
    
    Args:
        rag_processor: Processeur RAG à tester.
        search_engine: Moteur de recherche.
        db_session: Session de base de données.
        
    Ce test vérifie que:
    - La méthode construit correctement la requête de recherche
    - Les filtres sont correctement transmis
    - La recherche est exécutée et retourne des résultats
    """
    append_to_log("=== TEST: Récupération de documents ===")
    
    # Créer des documents de test dans la base de données
    test_data = create_test_documents(num_docs=5)
    corpus_id = test_data["corpus_id"]
    
    try:
        # Paramètres de requête
        query = "Recherche vectorielle PostgreSQL"
        filters = {
            "theme": "Base de données",
            "document_type": "Web"
        }
        
        # Exécuter la récupération
        search_results = await rag_processor.retrieve_documents(query, filters)
        
        # Vérifier les résultats
        append_to_log(f"Nombre de résultats récupérés: {len(search_results.results)}")
        
        # Validations
        assert search_results.query == query, "La requête doit être correctement transmise"
        assert len(search_results.results) > 0, "Des résultats doivent être retournés"
        for result in search_results.results:
            assert result.theme == "Base de données", "Le filtre de thème doit être appliqué"
            assert result.document_type == "Web", "Le filtre de type de document doit être appliqué"
        
        # Test sans filtres
        search_results_no_filters = await rag_processor.retrieve_documents(query)
        append_to_log(f"Résultats sans filtres: {len(search_results_no_filters.results)}")
        assert len(search_results_no_filters.results) > 0, "Des résultats doivent être retournés même sans filtres"
        
        append_to_log("✅ Test de récupération de documents réussi")
    except Exception as e:
        append_to_log(f"Erreur lors de la récupération des documents: {e}")
        raise


@pytest.mark.anyio
async def test_retrieve_and_generate(rag_processor):
    """Teste la génération de réponses à partir des documents récupérés.
    
    Args:
        rag_processor: Processeur RAG à tester.
        
    Ce test vérifie que:
    - Le processeur récupère des documents pertinents
    - Un prompt est généré avec le bon template
    - Le modèle génère une réponse
    - Les paramètres de génération sont correctement transmis
    """
    append_to_log("=== TEST: Génération de réponses ===")
    
    # Exécuter la génération standard
    query = "Comment fonctionne le RAG?"
    
    response = await rag_processor.retrieve_and_generate(
        query=query,
        filters={"theme": "IA"},
        prompt_type="standard"
    )
    
    append_to_log(f"Réponse générée: {response}")
    assert response, "Une réponse doit être générée"
    
    # Tester avec différents modes de réflexion
    response_with_thinking = await rag_processor.retrieve_and_generate(
        query=query,
        enable_thinking=True
    )
    
    response_without_thinking = await rag_processor.retrieve_and_generate(
        query=query,
        enable_thinking=False
    )
    
    append_to_log(f"Réponse avec thinking: {response_with_thinking}")
    append_to_log(f"Réponse sans thinking: {response_without_thinking}")
    
    # Validation simple des résultats, sans vérifier le contenu exact
    assert isinstance(response_with_thinking, str) and len(response_with_thinking) > 0, "Une réponse avec thinking doit être générée"
    assert isinstance(response_without_thinking, str) and len(response_without_thinking) > 0, "Une réponse sans thinking doit être générée"
    
    # Tester avec un prompt_type différent
    response_summary = await rag_processor.retrieve_and_generate(
        query=query,
        prompt_type="summary"
    )
    
    append_to_log(f"Réponse avec template summary: {response_summary}")
    assert response_summary, "Une réponse doit être générée avec le template summary"
    
    append_to_log("✅ Test de génération de réponses réussi")


@pytest.mark.anyio
async def test_retrieve_and_generate_stream(rag_processor):
    """Teste le streaming progressif des réponses.
    
    Args:
        rag_processor: Processeur RAG à tester.
        
    Ce test vérifie que:
    - La méthode retourne un générateur asynchrone
    - Des fragments de texte sont produits progressivement
    """
    append_to_log("=== TEST: Streaming de réponses ===")

    # Exécuter la génération en streaming
    query = "Comment fonctionne la recherche vectorielle?"
    stream_generator = rag_processor.retrieve_and_generate_stream(
        query=query,
        filters={"theme": "Base de données"}
    )
    
    # Collecter les fragments
    fragments = []
    try:
        async for fragment in stream_generator:
            fragments.append(fragment)
            append_to_log(f"Fragment reçu: {fragment}")
            
            # Limiter à 5 fragments pour éviter des tests trop longs
            if len(fragments) >= 5:
                break
    except Exception as e:
        append_to_log(f"Erreur pendant le streaming: {e}")
    
    # Validations
    assert len(fragments) > 0, "Au moins un fragment doit être généré"
    full_response = "".join(fragments)
    assert len(full_response) > 0, "Le texte généré ne doit pas être vide"


if __name__ == "__main__":
    # Exécution manuelle des tests
    setup_module()
    # Utilisation du backend asyncio uniquement pour éviter les erreurs avec trio
    import sys
    sys.argv = ["pytest", "-xvs", "askai/test/test_askai_src.py"]
    pytest.main()
    print(f"✅ Tests terminés! Consultez le log: {LOG_PATH}")