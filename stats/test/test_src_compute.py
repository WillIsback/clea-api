import logging

from datetime import datetime, timedelta
from pathlib import Path
from vectordb.src.database import get_db, SearchQuery

from stats import StatsComputer, DashboardStats, DocumentStats, SearchStats, SystemStats

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stats-tests")

# Chemin pour les logs de test
LOG_DIR = Path("stats/test/log")
LOG_PATH = LOG_DIR / "stats_test.log"



def setup_module():
    """Configure l'environnement pour les tests."""
    # Créer le répertoire de logs s'il n'existe pas
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Réinitialiser le fichier de log
    with open(LOG_PATH, "w") as f:
        f.write(f"=== Tests d'index démarrés le {datetime.now()} ===\n\n")


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

def generate_query():
    db = next(get_db())
    try:
        # Ajouter quelques requêtes de test
        queries = [
            {"query_text": "Intelligence artificielle", "results_count": 15, "confidence_level": 0.8},
            {"query_text": "Analyse de données", "results_count": 8, "confidence_level": 0.7},
            {"query_text": "Sécurité informatique", "results_count": 12, "confidence_level": 0.9},
            {"query_text": "Intelligence artificielle", "results_count": 10, "confidence_level": 0.75}
        ]
        
        for i, q in enumerate(queries):
            # Distribuer les dates sur les 90 derniers jours
            days_ago = (i * 15) % 90
            query = SearchQuery(
                query_text=q["query_text"],
                results_count=q["results_count"],
                confidence_level=q["confidence_level"],
                created_at=datetime.now() - timedelta(days=days_ago)
            )
            db.add(query)
        
        db.commit()
        print("Données de test ajoutées avec succès.")
    except Exception as e:
        db.rollback()
        print(f"Erreur lors de l'ajout des données de test: {str(e)}")
    finally:
        db.close()
        
def compute_document_stats(skip=0, limit=100) -> DocumentStats:
    """Calcule les statistiques des documents présents dans la base de données.
    
    Cette fonction récupère les documents de la base de données et calcule diverses statistiques
    comme le nombre total, la répartition par thème et par type, ainsi que les documents 
    récemment ajoutés et l'évolution en pourcentage.

    Args:
        skip: Nombre de documents à ignorer (pour la pagination).
        limit: Nombre maximal de documents à retourner.

    Returns:
        Un objet DocumentStats contenant les statistiques calculées.
    """
    stats_computer = StatsComputer()
    return stats_computer.compute_document_stats(skip, limit)
    
def compute_search_stats(skip=0, limit=100) -> SearchStats:
    """Calcule les statistiques des recherches effectuées dans le système.
    
    Cette fonction analyse l'historique des recherches pour fournir des métriques
    comme le nombre total de recherches, l'activité récente et les requêtes
    les plus populaires.

    Args:
        skip: Nombre d'entrées à ignorer pour la pagination.
        limit: Nombre maximal d'entrées à traiter.

    Returns:
        Un objet SearchStats contenant les statistiques calculées.
    """
    stats_computer = StatsComputer()
    return stats_computer.compute_search_stats(skip, limit)


def compute_system_stats() -> SystemStats:
    """Calcule les statistiques système globales.
    
    Cette fonction analyse les métriques de confiance des recherches effectuées
    et l'état des corpus dans le système pour fournir une vue d'ensemble
    de la performance et de l'état de l'indexation.
    
    Returns:
        Un objet SystemStats contenant les métriques système calculées.
    """
    stats_computer = StatsComputer()
    return stats_computer.compute_system_stats()


def compute_all_stats() -> DashboardStats:
    """Calcule toutes les statistiques pour le tableau de bord.
    
    Cette fonction agrège les résultats des différentes fonctions de calcul
    de statistiques pour fournir un objet unique contenant toutes les
    métriques nécessaires au tableau de bord.
    
    Returns:
        Un objet DashboardStats contenant l'ensemble des statistiques.
    """
    stats_computer = StatsComputer()
    return stats_computer.compute_all_stats()

def test_document_stats():
    """Test de la fonction compute_document_stats."""
    append_to_log("Démarrage du test compute_document_stats")


    # Appeler la fonction à tester
    stats = compute_document_stats()
    append_to_log("Voici les stats :")
    append_to_log(f"Total Count: {stats.total_count}")
    append_to_log(f"By Theme: {stats.by_theme}")
    append_to_log(f"By Type: {stats.by_type}")
    append_to_log(f"Recently Added: {stats.recently_added}")
    append_to_log(f"Percent Change: {stats.percent_change}")

    append_to_log("compute_document_stats exécuté avec succès")
    # Vérifier les résultats
    assert stats.total_count > 0, "Le nombre total de documents doit être supérieur à 0"
    assert isinstance(stats.by_theme, dict), "by_theme doit être un dictionnaire"
    assert isinstance(stats.by_type, dict), "by_type doit être un dictionnaire"
    assert stats.recently_added >= 0, "recently_added doit être supérieur ou égal à 0"
    assert 0 <= stats.percent_change <= 100, "percent_change doit être entre 0 et 100"

    append_to_log("Test compute_document_stats réussi")
    
def test_search_stats():
    """Test de la fonction compute_search_stats."""
    append_to_log("Démarrage du test compute_search_stats")
    # Appeler la fonction à tester
    stats = compute_search_stats()
    if stats.total_count == 0:
        append_to_log("Aucune donnée de recherche trouvée.")
        generate_query()
        stats = compute_search_stats()
        
    append_to_log("Voici les stats :")
    append_to_log(f"Total Count: {stats.total_count}")
    append_to_log(f"last month total_count: {stats.last_month_count}")
    append_to_log(f"Percent Change: {stats.percent_change}")
    append_to_log(f"Top Queries: {stats.top_queries}")

    append_to_log("compute_search_stats exécuté avec succès")
    # Vérifier les résultats
    assert stats.total_count > 0, "Le nombre total de requêtes doit être supérieur à 0"
    assert stats.last_month_count >= 0, "Le nombre de requêtes du mois dernier doit être supérieur ou égal à 0"
    assert 0 <= stats.percent_change <= 100, "percent_change doit être entre 0 et 100"
    assert isinstance(stats.top_queries, list), "top_queries doit être une liste"
    append_to_log("Test compute_search_stats réussi")
    
def test_system_stats():
    """Test de la fonction compute_system_stats."""
    append_to_log("Démarrage du test compute_system_stats")
    # Appeler la fonction à tester
    stats = compute_system_stats()
    append_to_log("Voici les stats :")
    append_to_log(f"Satisfaction: {stats.satisfaction}")
    append_to_log(f"Avg Confidence: {stats.avg_confidence}")
    append_to_log(f"Percent Change: {stats.percent_change}")
    append_to_log(f"Indexed Corpora: {stats.indexed_corpora}")
    append_to_log(f"Total Corpora: {stats.total_corpora}")

    append_to_log("compute_system_stats exécuté avec succès")
    # Vérifier les résultats
    assert 0 <= stats.satisfaction <= 100, "Satisfaction doit être entre 0 et 100"
    assert 0 <= stats.avg_confidence <= 100, "avg_confidence doit être entre 0 et 100"
    assert 0 <= stats.percent_change <= 100, "percent_change doit être entre 0 et 100"
    assert stats.indexed_corpora >= 0, "indexed_corpora doit être supérieur ou égal à 0"
    assert stats.total_corpora >= 0, "total_corpora doit être supérieur ou égal à 0"

    append_to_log("Test compute_system_stats réussi")