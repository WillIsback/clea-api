from vectordb.src.crud import get_documents
from vectordb.src.database import get_db, SearchQuery
from stats.src.stats_src_schemas import DocumentStats, SearchStats, SystemStats, DashboardStats
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
import logging


class StatsComputer:
    """Calculateur de statistiques pour le tableau de bord.
    
    Cette classe centralise les fonctionnalités de calcul des différentes
    métriques utilisées dans le tableau de bord d'administration.
    """
    
    def __init__(self):
        """Initialise le calculateur de statistiques."""
        self.logger = logging.getLogger("clea-api.stats")
    
    def _get_db_session(self) -> Session:
        """Récupère une session de base de données active.
        
        Returns:
            Une session SQLAlchemy active.
        """
        return next(get_db())
    
    def compute_document_stats(self, skip=0, limit=100) -> DocumentStats:
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
        db = self._get_db_session()
        documents = get_documents(db=db, skip=skip, limit=limit)
        
        total_count = len(documents)
        by_theme = {}
        by_type = {}
        recently_added = 0
        percent_change = 0.0
        
        for doc in documents:
            # Compter par thème
            if doc.theme not in by_theme:
                by_theme[doc.theme] = 0
            by_theme[doc.theme] += 1
            
            # Compter par type
            if doc.document_type not in by_type:
                by_type[doc.document_type] = 0
            by_type[doc.document_type] += 1
            
            # Compter les documents récemment ajoutés
            if doc.publish_date > (datetime.now() - timedelta(days=30)).date():
                recently_added += 1
                
        # Calcul du pourcentage d'évolution
        if total_count > 0:
            percent_change = (recently_added / total_count) * 100
        
        return DocumentStats(
            total_count=total_count,
            by_theme=by_theme,
            by_type=by_type,
            recently_added=recently_added,
            percent_change=percent_change
        )
    
    def compute_search_stats(self, skip=0, limit=100) -> SearchStats:
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
        db = self._get_db_session()
        
        try:
            # Nombre total de recherches
            total_count = db.query(SearchQuery).count()
            
            # Date limite pour le dernier mois
            one_month_ago = datetime.now() - timedelta(days=30)
            
            # Nombre de recherches du dernier mois
            last_month_count = db.query(SearchQuery).filter(
                SearchQuery.created_at >= one_month_ago
            ).count()
            
            # Calcul du pourcentage d'évolution
            percent_change = 0.0
            if total_count > 0:
                # Si nous avons deux mois complets de données
                two_months_ago = datetime.now() - timedelta(days=60)
                previous_month_count = db.query(SearchQuery).filter(
                    SearchQuery.created_at >= two_months_ago,
                    SearchQuery.created_at < one_month_ago
                ).count()
                
                if previous_month_count > 0:
                    percent_change = ((last_month_count - previous_month_count) / previous_month_count) * 100
            
            # Requêtes les plus populaires (top 10)
            top_queries_result = db.query(
                SearchQuery.query_text,
                func.count(SearchQuery.id).label('count')
            ).group_by(SearchQuery.query_text).order_by(
                func.count(SearchQuery.id).desc()
            ).limit(10).all()
            
            # Formatage des résultats pour les requêtes populaires
            top_queries = [
                {"query": query, "count": count}
                for query, count in top_queries_result
            ]
            
            return SearchStats(
                total_count=total_count,
                last_month_count=last_month_count,
                percent_change=percent_change,
                top_queries=top_queries
            )
        
        except Exception as e:
            # En cas d'erreur, retourner des statistiques par défaut
            self.logger.error(f"Erreur lors du calcul des statistiques de recherche: {str(e)}")
            
            return SearchStats(
                total_count=0,
                last_month_count=0,
                percent_change=0.0,
                top_queries=[]
            )
    
    def compute_system_stats(self) -> SystemStats:
        """Calcule les statistiques système globales.
        
        Cette fonction analyse les métriques de confiance des recherches effectuées
        et l'état des corpus dans le système pour fournir une vue d'ensemble
        de la performance et de l'état de l'indexation.
        
        Returns:
            Un objet SystemStats contenant les métriques système calculées.
        """
        db = self._get_db_session()
        
        try:
            # Calcul de la confiance moyenne sur les recherches
            one_month_ago = datetime.now() - timedelta(days=30)
            two_months_ago = datetime.now() - timedelta(days=60)
            
            # Confiance moyenne du mois actuel
            current_confidence = db.query(func.avg(SearchQuery.confidence_level)).filter(
                SearchQuery.created_at >= one_month_ago
            ).scalar() or 0.0
            
            # Confiance moyenne du mois précédent
            previous_confidence = db.query(func.avg(SearchQuery.confidence_level)).filter(
                SearchQuery.created_at >= two_months_ago,
                SearchQuery.created_at < one_month_ago
            ).scalar() or 0.0
            
            # Calcul du taux de satisfaction (basé sur la confiance)
            # On considère qu'une recherche avec confiance > 0.7 est satisfaisante
            satisfaction_count = db.query(func.count(SearchQuery.id)).filter(
                SearchQuery.confidence_level >= 0.7,
                SearchQuery.created_at >= one_month_ago
            ).scalar() or 0
            
            total_searches = db.query(func.count(SearchQuery.id)).filter(
                SearchQuery.created_at >= one_month_ago
            ).scalar() or 0
            
            satisfaction = (satisfaction_count / total_searches * 100) if total_searches > 0 else 0.0
            
            # Calcul de l'évolution de la confiance
            percent_change = 0.0
            if previous_confidence > 0:
                percent_change = ((current_confidence - previous_confidence) / previous_confidence) * 100
            
            # Statistiques sur les documents indexés
            # Utilisation de get_documents pour récupérer les documents avec leur statut d'indexation
            documents = get_documents(db=db, skip=0, limit=1000)  # Récupérer assez de documents
            
            # Compter les documents indexés (index_needed=False signifie que le document est indexé)
            indexed_documents = sum(1 for doc in documents if not doc.index_needed)
            total_documents = len(documents)
            
            return SystemStats(
                satisfaction=satisfaction,
                avg_confidence=current_confidence,
                percent_change=percent_change,
                indexed_corpora=indexed_documents,
                total_corpora=total_documents
            )
        
        except Exception as e:
            # En cas d'erreur, retourner des statistiques par défaut
            self.logger.error(f"Erreur lors du calcul des statistiques système: {str(e)}")
            
            return SystemStats(
                satisfaction=0.0,
                avg_confidence=0.0,
                percent_change=0.0,
                indexed_corpora=0,
                total_corpora=0
            )
    
    def compute_all_stats(self) -> DashboardStats:
        """Calcule toutes les statistiques pour le tableau de bord.
        
        Cette fonction agrège les résultats des différentes fonctions de calcul
        de statistiques pour fournir un objet unique contenant toutes les
        métriques nécessaires au tableau de bord.
        
        Returns:
            Un objet DashboardStats contenant l'ensemble des statistiques.
        """
        document_stats = self.compute_document_stats()
        search_stats = self.compute_search_stats()
        system_stats = self.compute_system_stats()
        
        return DashboardStats(
            document_stats=document_stats,
            search_stats=search_stats,
            system_stats=system_stats
        )

