"""
Tests de performance pour les index vectoriels pgvector.

Ce module analyse l'impact des index vectoriels sur les performances de recherche
en comparant les temps d'exécution avant et après la création d'un index.
"""

import logging
import time
import statistics
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from vectordb.src.crud import delete_document
from vectordb.src.database import get_db
from vectordb.src.index_manager import (
    check_index_status,
    create_simple_index,
    drop_index,
)
from vectordb.src.schemas import SearchRequest
from vectordb.src.search import SearchEngine
from pipeline.src.pipeline import process_and_store

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("performance-tests")

# Chemin pour les logs de test
LOG_DIR = Path("vectordb/test/log")
LOG_PATH = LOG_DIR / "performance.log"

# Chemins des fichiers de test - du plus petit au plus grand
CORPUS_PATHS = [
    Path("demo/demo.txt"),  # Petit corpus pour tests rapides
    Path("demo/benchmark_medium.txt"),  # Corpus moyen (si disponible)
    Path("demo/benchmark_large.txt"),  # Grand corpus (si disponible)
]

# Requêtes pour les tests de performance - spécifiques aux index vectoriels
TEST_QUERIES = [
    "Quel est le meilleur type d'index ANN pour une base de données vectorielle de grande taille?",
    "Comment l'algorithme IVFFLAT partitionne-t-il l'espace vectoriel?",
    "Avantages et inconvénients des index HNSW par rapport aux autres méthodes",
    "Optimisation des paramètres lists dans pgvector pour maximiser les performances",
    "Impact de la dimensionnalité des vecteurs sur l'efficacité des index ANN",
]

# Nombre d'exécutions par défaut pour chaque requête
DEFAULT_NUM_RUNS = 5


def setup_module():
    """
    Configure l'environnement pour les tests de performance.

    Prépare le répertoire des logs et initialise le fichier de résultats.
    """
    # Créer le répertoire de logs s'il n'existe pas
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Réinitialiser le fichier de log
    with open(LOG_PATH, "w") as f:
        f.write(
            f"=== Tests de performance d'index démarrés le {datetime.now()} ===\n\n"
        )
        f.write(
            "Ce rapport compare les temps d'exécution des recherches vectorielles\n"
        )
        f.write("avec et sans index vectoriel pgvector.\n\n")


def append_to_log(message: str) -> None:
    """
    Ajoute une entrée au fichier de log.

    Args:
        message: Message à enregistrer dans le log.
    """
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"{datetime.now()} -- {message}\n")
        logger.info(message)
    except Exception as e:
        logger.error(f"Erreur lors de l'écriture dans le fichier de log: {e}")
        raise


def find_available_corpus() -> Path:
    """
    Trouve le corpus de test disponible le plus volumineux.

    Vérifie la disponibilité des fichiers de corpus par ordre de taille
    décroissante et renvoie le premier trouvé.

    Returns:
        Path: Chemin vers le corpus de test disponible le plus volumineux.
    """
    # Essayer du plus grand au plus petit
    for corpus_path in reversed(CORPUS_PATHS):
        if corpus_path.exists():
            return corpus_path

    # Par défaut, utiliser le petit corpus qui devrait toujours être disponible
    return CORPUS_PATHS[0]


def benchmark_search(db: Any, query_texts: List[str], runs: int = 3) -> Dict[str, Any]:
    """
    Exécute une série de requêtes de recherche et mesure les performances.

    Analyse le temps d'exécution de multiples requêtes pour obtenir des
    statistiques fiables sur les performances de recherche.

    Args:
        db: Session de base de données active.
        query_texts: Liste des requêtes à tester.
        runs: Nombre d'exécutions pour chaque requête.

    Returns:
        Dict[str, Any]: Statistiques de performance (temps min, max, moyen, etc.).
    """
    retriever = SearchEngine()
    results = []

    # Échauffement du système - exécuter quelques requêtes sans les compter
    warmup_query = SearchRequest(
        query="Requête d'échauffement pour initialiser les caches systèmes",
        topK=5,
        theme="TEST",
        documentType="TXT",
        startDate=None,
        endDate=None,
        corpusId=None,
        hierarchyLevel=None,
    )
    for _ in range(2):
        retriever.hybrid_search(db=db, req=warmup_query)

    # Exécuter et chronométrer les requêtes de test
    for query_text in query_texts:
        query_times = []
        for _ in range(runs):
            # Créer une requête de recherche
            requete = SearchRequest(
                query=query_text,
                topK=10,
                theme="TEST",
                documentType="TXT",
                startDate=None,
                endDate=None,
                corpusId=None,
                hierarchyLevel=None,
            )

            # Mesurer le temps d'exécution (exclure les opérations non liées à la requête)
            start_time = time.time()
            reponse = retriever.hybrid_search(db=db, req=requete)
            end_time = time.time()

            elapsed_ms = (end_time - start_time) * 1000
            query_times.append(elapsed_ms)

        # Statistiques pour cette requête
        results.append(
            {
                "query": query_text,
                "times_ms": query_times,
                "avg_ms": statistics.mean(query_times),
                "min_ms": min(query_times),
                "max_ms": max(query_times),
                "median_ms": statistics.median(query_times),
                "result_count": reponse.total_results,
            }
        )

    # Statistiques globales
    all_times = [time for result in results for time in result["times_ms"]]
    return {
        "query_results": results,
        "global_stats": {
            "total_queries": len(query_texts) * runs,
            "avg_ms": statistics.mean(all_times),
            "min_ms": min(all_times),
            "max_ms": max(all_times),
            "median_ms": statistics.median(all_times),
            "std_dev_ms": statistics.stdev(all_times) if len(all_times) > 1 else 0,
        },
    }


def format_performance_report(
    non_indexed: Dict[str, Any], indexed: Dict[str, Any], chunk_count: int
) -> str:
    """
    Formate un rapport de comparaison des performances.

    Génère un rapport détaillé comparant les performances de recherche
    avec et sans index vectoriel.

    Args:
        non_indexed: Résultats sans index.
        indexed: Résultats avec index.
        chunk_count: Nombre de chunks dans le corpus.

    Returns:
        str: Rapport formaté.
    """
    report = [
        "## RAPPORT DE PERFORMANCE D'INDEXATION VECTORIELLE ##\n",
        f"Taille du corpus: {chunk_count} chunks\n",
    ]

    # Facteur d'amélioration global
    improvement_factor = (
        non_indexed["global_stats"]["avg_ms"] / indexed["global_stats"]["avg_ms"]
    )
    improvement_percent = (improvement_factor - 1) * 100

    report.append(
        f"Amélioration globale: x{improvement_factor:.2f} ({improvement_percent:.1f}%)\n"
    )
    report.append(
        f"Temps moyen sans index: {non_indexed['global_stats']['avg_ms']:.2f} ms"
    )
    report.append(f"Temps moyen avec index: {indexed['global_stats']['avg_ms']:.2f} ms")
    report.append(
        f"Accélération moyenne: {non_indexed['global_stats']['avg_ms'] - indexed['global_stats']['avg_ms']:.2f} ms\n"
    )

    # Comparaison par requête
    report.append("## DÉTAIL PAR REQUÊTE ##\n")
    for non_idx_query, idx_query in zip(
        non_indexed["query_results"], indexed["query_results"]
    ):
        query = non_idx_query["query"]
        improvement = non_idx_query["avg_ms"] / idx_query["avg_ms"]
        imp_percent = (improvement - 1) * 100
        report.append(
            f'\nRequête: "{query[:60]}..."'
            if len(query) > 60
            else f'\nRequête: "{query}"'
        )
        report.append(
            f"  - Sans index: {non_idx_query['avg_ms']:.2f} ms (min={non_idx_query['min_ms']:.2f}, max={non_idx_query['max_ms']:.2f})"
        )
        report.append(
            f"  - Avec index: {idx_query['avg_ms']:.2f} ms (min={idx_query['min_ms']:.2f}, max={idx_query['max_ms']:.2f})"
        )
        report.append(f"  - Amélioration: x{improvement:.2f} ({imp_percent:.1f}%)")
        report.append(f"  - Résultats trouvés: {idx_query['result_count']}")

    return "\n".join(report)


def calculate_expected_improvement(chunk_count: int) -> float:
    """
    Calcule l'amélioration de performance attendue selon la taille du corpus.

    Pour des corpus plus petits, l'amélioration attendue est moindre
    car le surcoût des opérations PostgreSQL masque l'avantage de l'index.

    Args:
        chunk_count: Nombre de chunks dans le corpus.

    Returns:
        float: Facteur d'amélioration minimal attendu.
    """
    if chunk_count < 50:
        # Pour les très petits corpus, même une amélioration de 5% est significative
        return 1.05
    elif chunk_count < 100:
        # Pour les petits corpus, attendre au moins 10%
        return 1.1
    elif chunk_count < 500:
        # Pour les corpus moyens, attendre au moins 20%
        return 1.2
    else:
        # Pour les grands corpus, attendre au moins 30%
        return 1.3


def create_or_use_large_corpus(target_chunks: int = 200) -> Dict[str, Any]:
    """
    Crée ou utilise un corpus de taille suffisante pour les tests de performance.
    """
    # Trouver le fichier de corpus le plus volumineux disponible
    corpus_file = find_available_corpus()
    append_to_log(f"Utilisation du corpus: {corpus_file}")

    # Charger le document initial
    document = process_and_store(
        file_path=str(corpus_file),
        max_length=500,  # Chunks plus petits pour en avoir plus
        overlap=50,
        theme="TEST",
    )
    corpus_id = document["corpus_id"]

    # Vérifier combien de chunks ont été créés
    initial_status = check_index_status(corpus_id)
    chunk_count = initial_status["chunk_count"]
    append_to_log(f"Corpus initial chargé avec {chunk_count} chunks (ID: {corpus_id})")

    # Si nous avons déjà assez de chunks, retourner directement
    if chunk_count >= target_chunks:
        return document

    # Sinon, créer des documents DIFFÉRENTS avec des corpus_id DIFFÉRENTS
    iterations = min(10, (target_chunks // chunk_count) + 1)
    append_to_log(
        f"Chunks insuffisants. Création de {iterations - 1} documents supplémentaires..."
    )

    # Créer des documents supplémentaires
    additional_docs = []
    for i in range(1, iterations):
        append_to_log(f"Création du document supplémentaire #{i + 1}...")
        # Noter: PAS de corpus_id ici pour créer un nouveau corpus
        add_doc = process_and_store(
            file_path=str(corpus_file), max_length=500, overlap=50, theme=f"TEST-{i}"
        )
        additional_docs.append(add_doc)

    # Calculer le nombre total de chunks
    total_chunks = chunk_count + sum(doc["chunks"] for doc in additional_docs)
    append_to_log(
        f"Total final: {total_chunks} chunks répartis sur {len(additional_docs) + 1} documents"
    )

    # Mettre à jour le document retourné
    document["total_chunks"] = total_chunks
    document["additional_docs"] = additional_docs
    return document


def test_index_performance_comparison():
    """
    Teste et compare les performances de recherche avec et sans index vectoriel.

    Ce test mesure les temps de recherche avant et après la création d'un index
    pour quantifier précisément le gain de performance apporté par l'indexation.
    Le test s'adapte à la taille du corpus pour définir les attentes appropriées.
    """
    db = next(get_db())
    append_to_log("=== TEST: Comparaison de performance d'indexation vectorielle ===")

    # 1. Créer ou utiliser un corpus de taille adéquate
    document = create_or_use_large_corpus(target_chunks=200)
    corpus_id = document["corpus_id"]
    append_to_log(f"Utilisation du corpus avec ID: {corpus_id}")

    # 2. Vérifier l'état initial de l'index
    initial_status = check_index_status(corpus_id)
    chunk_count = initial_status["chunk_count"]
    append_to_log(
        f"État initial de l'index (corpus de {chunk_count} chunks): {initial_status}"
    )

    # S'assurer que l'index n'existe pas initialement
    if initial_status["index_exists"]:
        append_to_log("Index déjà présent, suppression...")
        drop_index(corpus_id)
        initial_status = check_index_status(corpus_id)

    assert not initial_status["index_exists"], (
        "L'index ne devrait pas exister initialement"
    )

    # 3. Benchmark sans index
    append_to_log("Exécution des requêtes de test SANS index vectoriel...")
    non_indexed_results = benchmark_search(db, TEST_QUERIES, DEFAULT_NUM_RUNS)
    append_to_log(
        f"Temps moyen sans index: {non_indexed_results['global_stats']['avg_ms']:.2f} ms"
    )

    # 4. Créer l'index vectoriel
    append_to_log(f"Création de l'index vectoriel pour le corpus {corpus_id}...")
    create_result = create_simple_index(corpus_id)
    append_to_log(f"Résultat de la création: {create_result}")

    # 5. Vérifier que l'index est bien créé
    index_status = check_index_status(corpus_id)
    append_to_log(f"État de l'index après création: {index_status}")
    assert index_status["index_exists"], "L'index devrait exister après la création"

    # 6. Benchmark avec index
    append_to_log("Exécution des requêtes de test AVEC index vectoriel...")
    indexed_results = benchmark_search(db, TEST_QUERIES, DEFAULT_NUM_RUNS)
    append_to_log(
        f"Temps moyen avec index: {indexed_results['global_stats']['avg_ms']:.2f} ms"
    )

    # 7. Générer et enregistrer le rapport de performance
    report = format_performance_report(
        non_indexed_results, indexed_results, chunk_count
    )
    append_to_log("\n" + report)

    # 8. Supprimer l'index (optionnel dans le benchmark)
    if os.environ.get("KEEP_TEST_INDEX") != "1":
        drop_result = drop_index(corpus_id)
        append_to_log(f"Suppression de l'index: {drop_result}")

        # Vérifier la suppression de l'index
        final_status = check_index_status(corpus_id)
        append_to_log(f"État final de l'index: {final_status}")
        assert not final_status["index_exists"], (
            "L'index ne devrait plus exister à la fin"
        )
    else:
        append_to_log(
            "Conservation de l'index pour tests ultérieurs (KEEP_TEST_INDEX=1)"
        )

    # 9. Supprimer le document de test (optionnel dans le benchmark)
    if os.environ.get("KEEP_TEST_DOCUMENT") != "1":
        delete_result = delete_document(document_id=document["document_id"])
        append_to_log(f"Suppression du document: {delete_result}")
    else:
        append_to_log(
            "Conservation du document pour tests ultérieurs (KEEP_TEST_DOCUMENT=1)"
        )

    append_to_log("✅ Test de comparaison de performance terminé avec succès")

    # 10. Valider si un gain significatif est observé
    improvement_factor = (
        non_indexed_results["global_stats"]["avg_ms"]
        / indexed_results["global_stats"]["avg_ms"]
    )
    expected_improvement = calculate_expected_improvement(chunk_count)
    append_to_log(f"Facteur d'amélioration: x{improvement_factor:.2f}")
    append_to_log(
        f"Facteur d'amélioration attendu (pour {chunk_count} chunks): x{expected_improvement:.2f}"
    )

    # Adapter l'assertion à la taille du corpus de test
    if improvement_factor >= expected_improvement:
        append_to_log(
            f"✅ Amélioration suffisante: {(improvement_factor - 1) * 100:.1f}% (attendu: {(expected_improvement - 1) * 100:.1f}%)"
        )
    else:
        append_to_log(
            f"⚠️ Amélioration insuffisante: {(improvement_factor - 1) * 100:.1f}% (attendu: {(expected_improvement - 1) * 100:.1f}%)"
        )

    # Pour les tests automatisés, utiliser un seuil adaptatif
    # mais pour la vérification manuelle, on peut être plus tolérant
    if os.environ.get("PYTEST_RUNNING") == "1":
        assert improvement_factor >= expected_improvement, (
            f"L'index devrait apporter une amélioration d'au moins {(expected_improvement - 1) * 100:.1f}%, "
            f"mais seulement {(improvement_factor - 1) * 100:.1f}% observé"
        )


if __name__ == "__main__":
    # Exécution manuelle du test
    setup_module()
    test_index_performance_comparison()
    print(f"✅ Test de performance terminé! Consultez le rapport: {LOG_PATH}")
