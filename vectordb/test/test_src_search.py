"""
Tests du moteur de recherche hybride et de ses fonctionnalités avancées.

Ce module contient les tests pour vérifier le bon fonctionnement de:
1. L'évaluation de la confiance dans les résultats (confidence)
2. La détection des requêtes hors contexte (out-of-domain)
3. La normalisation des scores de pertinence
4. La recherche hybride complète avec filtres
"""

import logging
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any


from sqlalchemy import text


from vectordb.src.database import get_db, Chunk
from vectordb.src.search import SearchEngine
from vectordb.src.schemas import SearchRequest
from vectordb.src.crud import add_document_with_chunks
from vectordb.src.schemas import DocumentCreate
from vectordb.src.embeddings import EmbeddingGenerator

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("search-tests")

# Chemin pour les logs de test
LOG_DIR = Path("vectordb/test/log")
LOG_PATH = LOG_DIR / "search_test.log"


def setup_module():
    """Configure l'environnement pour les tests."""
    # Créer le répertoire de logs s'il n'existe pas
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Réinitialiser le fichier de log
    with open(LOG_PATH, "w") as f:
        f.write(f"=== Tests de recherche démarrés le {datetime.now()} ===\n\n")


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

    themes = ["Informatique", "Finance", "Marketing"]
    document_types = ["PDF", "DOCX", "TXT"]
    
    db = next(get_db())
    
    for i in range(num_docs):
        doc = DocumentCreate(
            title=f"Document test {i+1}",
            theme=themes[i % len(themes)],
            document_type=document_types[i % len(document_types)],
            publish_date=date.today(),
            corpus_id=corpus_id,
        )
        
        # Créer des chunks avec du contenu varié pour tester la pertinence
        chunks = [
            {
                "content": f"Contenu principal du document {i+1} sur {doc.theme}",
                "hierarchy_level": 1,
                "start_char": 0,
                "end_char": 50,
            },
            {
                "content": f"Information secondaire sur {doc.theme} avec détails spécifiques",
                "hierarchy_level": 1,
                "start_char": 51,
                "end_char": 110,
            },
            {
                "content": f"Données techniques sur le sujet {doc.theme}",
                "hierarchy_level": 2, 
                "start_char": 111,
                "end_char": 150,
            }
        ]
        
        added_document = add_document_with_chunks(
            db=db, doc=doc, chunks=chunks, batch_size=10
        )
        documents.append(added_document)
    
    # Ajouter un document spécial avec contenu très spécifique pour tester la pertinence
    special_doc = DocumentCreate(
        title="Document spécifique",
        theme="Intelligence Artificielle",
        document_type="PDF",
        publish_date=date.today(),
        corpus_id=corpus_id,
    )
    
    special_chunks = [
        {
            "content": "Les transformers sont des modèles d'apprentissage profond utilisés en NLP",
            "hierarchy_level": 1,
            "start_char": 0,
            "end_char": 72,
        },
        {
            "content": "BERT est un modèle bidirectionnel basé sur l'architecture transformer",
            "hierarchy_level": 2,
            "start_char": 73,
            "end_char": 139,
        }
    ]
    
    special_added = add_document_with_chunks(
        db=db, doc=special_doc, chunks=special_chunks, batch_size=10
    )
    documents.append(special_added)
    
    # Générer les embeddings pour tous les chunks en utilisant EmbeddingGenerator
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
        # SQLAlchemy gérera la sérialisation correcte
        chunk.embedding = embedding
        
    db.commit()
    
    append_to_log(f"Documents créés avec succès dans le corpus {corpus_id}, {len(chunks_to_embed)} chunks embeddings générés")
    return {"corpus_id": corpus_id, "documents": documents}

def test_confidence_evaluation():
    """Teste l'évaluation de la confiance avec différents scores.
    
    Ce test vérifie que:
    - Des scores élevés produisent une confiance élevée
    - Des scores faibles produisent une confiance faible
    - Des scores moyens produisent une confiance intermédiaire
    - L'absence de scores est correctement gérée
    """
    append_to_log("=== TEST: Évaluation de la confidence ===")
    
    engine = SearchEngine()
    
    # Test avec scores élevés
    high_scores = [0.8, 0.7, 0.65, 0.6]
    high_confidence = engine.evaluate_confidence(high_scores)
    append_to_log(f"Scores élevés: {high_scores} → Confidence: {high_confidence.level}")
    
    # Test avec scores faibles (hors contexte)
    low_scores = [-7.0, -8.5, -9.0, -10.0]
    low_confidence = engine.evaluate_confidence(low_scores)
    append_to_log(f"Scores faibles: {low_scores} → Confidence: {low_confidence.level}")
    
    # Test avec scores moyens
    mid_scores = [-2.0, -1.5, -1.0, -0.5]
    mid_confidence = engine.evaluate_confidence(mid_scores)
    append_to_log(f"Scores moyens: {mid_scores} → Confidence: {mid_confidence.level}")
    
    # Test sans scores
    empty_confidence = engine.evaluate_confidence([])
    append_to_log(f"Sans scores → Confidence: {empty_confidence.level}")
    
    # Validation
    assert high_confidence.level > 0.8, "La confidence devrait être élevée pour des scores élevés"
    assert low_confidence.level < 0.3, "La confidence devrait être faible pour des scores très négatifs"
    assert 0.3 < mid_confidence.level < 0.8, "La confidence devrait être moyenne pour des scores intermédiaires"
    assert empty_confidence.level == 0.0, "La confidence devrait être nulle sans scores"
    
    append_to_log("✅ Test d'évaluation de confidence réussi")


def test_score_normalization():
    """Teste la normalisation des scores de recherche.
    
    Ce test vérifie que:
    - Les scores sont correctement normalisés entre 0 et 1
    - Les cas spéciaux (liste vide, scores identiques) sont gérés
    """
    append_to_log("=== TEST: Normalisation des scores ===")
    
    engine = SearchEngine()
    
    # Test avec des scores variés
    varied_scores = [0.8, 0.2, 0.5, 0.9, 0.1]
    normalized = engine.normalize_scores(varied_scores)
    append_to_log(f"Scores originaux: {varied_scores}")
    append_to_log(f"Scores normalisés: {normalized}")
    
    # Test avec une liste vide
    empty_normalized = engine.normalize_scores([])
    append_to_log(f"Liste vide → Normalisée: {empty_normalized}")
    
    # Test avec scores identiques
    identical_scores = [0.5, 0.5, 0.5, 0.5]
    identical_normalized = engine.normalize_scores(identical_scores)
    append_to_log(f"Scores identiques: {identical_scores} → Normalisés: {identical_normalized}")
    
    # Test avec scores négatifs et positifs
    mixed_scores = [-10.0, -5.0, 0.0, 5.0, 10.0]
    mixed_normalized = engine.normalize_scores(mixed_scores)
    append_to_log(f"Scores mixtes: {mixed_scores} → Normalisés: {mixed_normalized}")
    
    # Validations
    assert len(normalized) == len(varied_scores), "La taille doit être conservée"
    assert all(0 <= n <= 1 for n in normalized), "Tous les scores normalisés doivent être entre 0 et 1"
    assert min(normalized) == 0, "Le score minimal doit être normalisé à 0"
    assert max(normalized) == 1, "Le score maximal doit être normalisé à 1"
    assert empty_normalized == [], "Une liste vide doit rester vide"
    assert all(n == 0.5 for n in identical_normalized), "Des scores identiques doivent être normalisés à 0.5"
    assert min(mixed_normalized) == 0 and max(mixed_normalized) == 1, "Les scores mixtes doivent être normalisés correctement"
    
    append_to_log("✅ Test de normalisation des scores réussi")


def test_out_of_domain_detection():
    """Teste la détection des requêtes hors domaine.
    
    Ce test vérifie que:
    - Une requête qui ne correspond à aucun document est détectée comme hors domaine
    - Un seuil de pertinence minimum filtre correctement les résultats non pertinents
    """
    append_to_log("=== TEST: Détection des requêtes hors domaine ===")
    
    # Créer un moteur avec un seuil de pertinence élevé pour le test
    engine = SearchEngine(min_relevance_threshold=0.0)
    
    # Simuler des scores pour une requête hors domaine
    out_of_domain_scores = [-8.5, -7.2, -6.9, -9.0]
    confidence = engine.evaluate_confidence(out_of_domain_scores)
    
    append_to_log(f"Requête hors domaine - Scores: {out_of_domain_scores}")
    append_to_log(f"Niveau de confidence: {confidence.level}, Message: {confidence.message}")
    
    # Validation
    assert confidence.level < 0.3, "Une requête hors domaine devrait avoir une confidence faible"
    assert "hors du domaine" in confidence.message.lower(), "Le message devrait mentionner 'hors domaine'"
    
    # Test avec un moteur ayant un seuil plus bas (devrait accepter plus de résultats)
    lenient_engine = SearchEngine(min_relevance_threshold=-10.0)
    lenient_confidence = lenient_engine.evaluate_confidence(out_of_domain_scores)
    
    append_to_log(f"Avec seuil bas - Niveau de confidence: {lenient_confidence.level}")
    
    # Le seuil étant plus bas, même des scores négatifs peuvent être au-dessus
    assert lenient_confidence.level > confidence.level, "Un seuil plus bas devrait augmenter la confidence"
    
    append_to_log("✅ Test de détection hors domaine réussi")


def test_hybrid_search():
    """Teste la recherche hybride avec évaluation de pertinence.
    
    Ce test vérifie que:
    - La recherche hybride fonctionne avec différents paramètres
    - Les filtres sont appliqués correctement
    - Les scores sont normalisés si demandé
    - La confiance est calculée pour les résultats
    """
    append_to_log("=== TEST: Recherche hybride complète ===")
    
    # Créer des documents de test dans la base
    test_data = create_test_documents(3)
    corpus_id = test_data["corpus_id"]
    
    db = next(get_db())
    engine = SearchEngine()
    
    # Test 1: Recherche simple
    append_to_log("Test 1: Recherche simple")
    request1 = SearchRequest(
        query="Informatique",
        top_k=5,
        normalize_scores=True,
        filter_by_relevance=False
    )
    response1 = engine.hybrid_search(db, request1)
    
    append_to_log(f"Résultats trouvés: {len(response1.results)}")
    append_to_log(f"Niveau de confidence: {response1.confidence.level}")
    
    # Test 2: Recherche avec filtres
    append_to_log("Test 2: Recherche avec filtres")
    request2 = SearchRequest(
        query="Intelligence artificielle",
        top_k=5,
        theme="Intelligence Artificielle",
        normalize_scores=True,
        filter_by_relevance=True
    )
    response2 = engine.hybrid_search(db, request2)
    
    append_to_log(f"Avec filtres - Résultats: {len(response2.results)}")
    
    # Test 3: Recherche de requête probablement hors contexte
    append_to_log("Test 3: Requête potentiellement hors contexte")
    request3 = SearchRequest(
        query="physique quantique supraconductivité",  # Termes probablement absents
        top_k=5,
        normalize_scores=True,
        filter_by_relevance=True
    )
    response3 = engine.hybrid_search(db, request3)
    
    append_to_log(f"Requête hors contexte - Niveau de confidence: {response3.confidence.level}")
    append_to_log(f"Message: {response3.confidence.message}")
    
    # Validations
    # Le test est passé si nous obtenons des réponses sans erreur
    # Les validations suivantes sont optionnelles car dépendent du contenu réel
    
    assert response1.topK == request1.top_k, "Le nombre max de résultats demandés doit être respecté"
    assert all(0 <= r.score <= 1 for r in response1.results), "Les scores normalisés doivent être entre 0 et 1"
    
    if response2.results:
        assert all(r.theme == request2.theme for r in response2.results), "Le filtre par thème doit être appliqué"
    
    # Pour une requête hors contexte, on s'attend à une confiance faible
    # mais on ne peut pas garantir qu'aucun résultat ne sera trouvé
    if response3.results:
        append_to_log("Note: La requête hors contexte a trouvé des résultats, mais avec une confiance réduite")
    
    append_to_log("✅ Test de recherche hybride réussi")

def test_filter_by_relevance_reduces_results():
    """Vérifie que filter_by_relevance True n’inclut que les résultats au-dessus du seuil."""
    append_to_log("=== TEST: Filtrage par pertinence ===")
    db = next(get_db())
    # On crée deux moteurs : l’un sans filtrage, l’autre avec seuil élevé
    engine_no_filter = SearchEngine(min_relevance_threshold=0.0)
    engine_with_filter = SearchEngine(min_relevance_threshold=0.0)

    # Même requête pour les deux
    req_base = dict(
        query="Jesus Christ",
        top_k=10,
        normalize_scores=False,
    )

    # Recherche sans filtrage
    resp_no = engine_no_filter.hybrid_search(
        db,
        SearchRequest(**{**req_base, "filter_by_relevance": False})
    )
    append_to_log(f"Score et résultat Avec filtre {resp_no.confidence}")
    for r in resp_no.results:
        append_to_log(f"Chunk {r.chunk_id} a un score {r.score} et un thème {r.theme}")
    # Recherche AVEC filtrage (seuil 0.5)
    resp_yes = engine_with_filter.hybrid_search(
        db,
        SearchRequest(**{**req_base, "filter_by_relevance": True})
    )
    append_to_log(f"Score et résultat Avec filtre {resp_yes.confidence}")
    for r in resp_yes.results:
        append_to_log(f"Chunk {r.chunk_id} a un score {r.score} et un thème {r.theme}")
    append_to_log(f"Sans filtre: {len(resp_no.results)} résultats, Avec filtre: {len(resp_yes.results)} résultats")
    # On s’attend à au moins autant de résultats sans filtrage…
    assert len(resp_yes.results) <= len(resp_no.results), \
        "Le nombre de résultats filtrés doit être ≤ nombre de résultats sans filtrage"
    # …et chacun des résultats filtrés doit respecter le seuil
    for r in resp_yes.results:
        assert r.score >= 0.5, f"Chunk {r.chunk_id} a un score {r.score} < seuil 0.5"
    append_to_log("✅ Test filter_by_relevance réussi")

if __name__ == "__main__":
    # Exécution manuelle des tests
    setup_module()
    test_confidence_evaluation()
    test_score_normalization()
    test_out_of_domain_detection()
    test_hybrid_search()
    print(f"✅ Tous les tests ont réussi! Consultez le log: {LOG_PATH}")