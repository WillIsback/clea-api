"""
stats_api_endpoint.py - Points d'accès FastAPI pour les statistiques de Cléa-API.

Ce module expose les fonctions de calcul de statistiques via des endpoints REST
permettant de consulter les métriques du système depuis l'interface d'administration.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from stats.src.stats_src_compute import (
    StatsComputer
)

from stats.src.stats_src_schemas import (
    DocumentStats,
    SearchStats,
    SystemStats,
    DashboardStats
)

from vectordb.src.database import get_db
from datetime import datetime

router = APIRouter()


# --------------------------------------------------------------------------- #
#  STATISTIQUES DES DOCUMENTS
# --------------------------------------------------------------------------- #
@router.get(
    "/documents",
    summary="Statistiques sur les documents",
    response_model=DocumentStats,
)
def get_document_stats(
    skip: int = Query(0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(100, description="Nombre maximal d'éléments à retourner"),
    db: Session = Depends(get_db),
):
    """Récupère les statistiques sur les documents présents dans la base de données.
    
    Cette route calcule différentes métriques sur les documents indexés, notamment
    la distribution par thème, par type de document, ainsi que les tendances
    récentes d'ajout de documents.
    
    Args:
        skip: Nombre d'éléments à ignorer pour la pagination.
        limit: Nombre maximal d'éléments à retourner.
        db: Session de base de données fournie par dépendance.
        
    Returns:
        DocumentStats: Objet contenant les statistiques sur les documents.
        
    Raises:
        HTTPException: Si une erreur survient lors du calcul des statistiques.
    """
    try:
        # Créer une instance de StatsComputer qui va recalculer toutes les métriques
        stats_computer = StatsComputer()
        return stats_computer.compute_document_stats(skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, 
                          detail=f"Erreur lors du calcul des statistiques de documents: {str(e)}")


# --------------------------------------------------------------------------- #
#  STATISTIQUES DES RECHERCHES
# --------------------------------------------------------------------------- #
@router.get(
    "/searches",
    summary="Statistiques sur les recherches effectuées",
    response_model=SearchStats,
)
def get_search_stats(
    skip: int = Query(0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(100, description="Nombre maximal d'éléments à retourner"),
    db: Session = Depends(get_db),
):
    """Récupère les statistiques sur les recherches effectuées dans le système.
    
    Cette route analyse l'historique des recherches pour fournir des métriques
    comme le nombre total de recherches, l'activité récente et les requêtes
    les plus populaires.
    
    Args:
        skip: Nombre d'éléments à ignorer pour la pagination.
        limit: Nombre maximal d'éléments à retourner.
        db: Session de base de données fournie par dépendance.
        
    Returns:
        SearchStats: Objet contenant les statistiques sur les recherches.
        
    Raises:
        HTTPException: Si une erreur survient lors du calcul des statistiques.
    """
    try:
        # Créer une instance de StatsComputer qui va recalculer toutes les métriques
        stats_computer = StatsComputer()
        return stats_computer.compute_search_stats(skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, 
                          detail=f"Erreur lors du calcul des statistiques de recherches: {str(e)}")


# --------------------------------------------------------------------------- #
#  STATISTIQUES SYSTÈME
# --------------------------------------------------------------------------- #
@router.get(
    "/system",
    summary="Statistiques système globales",
    response_model=SystemStats,
)
def get_system_stats(db: Session = Depends(get_db)):
    """Récupère les statistiques système globales.
    
    Cette route analyse les métriques de confiance des recherches effectuées
    et l'état des corpus dans le système pour fournir une vue d'ensemble
    de la performance et de l'état de l'indexation.
    
    Args:
        db: Session de base de données fournie par dépendance.
        
    Returns:
        SystemStats: Objet contenant les métriques système.
        
    Raises:
        HTTPException: Si une erreur survient lors du calcul des statistiques.
    """
    try:
        # Créer une instance de StatsComputer qui va recalculer toutes les métriques
        stats_computer = StatsComputer()
        return stats_computer.compute_system_stats()
    except Exception as e:
        raise HTTPException(status_code=500, 
                          detail=f"Erreur lors du calcul des statistiques système: {str(e)}")


# --------------------------------------------------------------------------- #
#  TOUTES LES STATISTIQUES (DASHBOARD)
# --------------------------------------------------------------------------- #
@router.get(
    "/dashboard",
    summary="Toutes les statistiques pour le tableau de bord",
    response_model=DashboardStats,
)
def get_all_stats(db: Session = Depends(get_db)):
    """Récupère l'ensemble des statistiques pour le tableau de bord.
    
    Cette route agrège les résultats des différentes fonctions de calcul
    de statistiques pour fournir un objet unique contenant toutes les
    métriques nécessaires au tableau de bord d'administration.
    
    Args:
        db: Session de base de données fournie par dépendance.
        
    Returns:
        DashboardStats: Objet contenant l'ensemble des statistiques.
        
    Raises:
        HTTPException: Si une erreur survient lors du calcul des statistiques.
    """
    try:
        # Créer une instance de StatsComputer qui va recalculer toutes les métriques
        stats_computer = StatsComputer()
        return stats_computer.compute_all_stats()
    except Exception as e:
        raise HTTPException(status_code=500, 
                          detail=f"Erreur lors du calcul des statistiques du tableau de bord: {str(e)}")


# --------------------------------------------------------------------------- #
#  RAFRAÎCHISSEMENT DU CACHE DE STATISTIQUES
# --------------------------------------------------------------------------- #
@router.post(
    "/refresh",
    summary="Rafraîchir le cache des statistiques",
    response_model=dict,
)
def refresh_stats_cache(db: Session = Depends(get_db)):
    """Force le rafraîchissement du cache des statistiques.
    
    Cette route permet d'invalider les caches potentiels et de forcer
    un recalcul complet de toutes les métriques du système. Utile après
    des opérations importantes comme des imports massifs ou des maintenances.
    
    Args:
        db: Session de base de données fournie par dépendance.
        
    Returns:
        dict: Résultat de l'opération avec statut et message.
        
    Raises:
        HTTPException: Si une erreur survient lors du rafraîchissement.
    """
    try:
        # Créer une instance de StatsComputer qui va recalculer toutes les métriques
        stats_computer = StatsComputer()
        stats_computer.compute_all_stats()
        
        return {
            "status": "success",
            "message": "Cache des statistiques rafraîchi avec succès",
            "timestamp": str(datetime.now())
        }
    except Exception as e:
        raise HTTPException(status_code=500, 
                          detail=f"Erreur lors du rafraîchissement du cache: {str(e)}")