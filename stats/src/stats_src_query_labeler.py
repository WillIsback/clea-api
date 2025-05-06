from typing import List, Dict, Set
import re


class QueryLabeler:
    """Labellisation des requêtes de recherche par extraction de mots-clés.
    
    Cette classe permet de transformer des requêtes longues en étiquettes concises
    pour une meilleure visualisation dans les statistiques et tableaux de bord.
    """
    
    def __init__(self, min_word_length: int = 3, max_label_length: int = 50, 
                stopwords_file: str = None) -> None:
        """Initialise le module de labellisation des requêtes.
        
        Args:
            min_word_length: Longueur minimale des mots à considérer comme significatifs.
            max_label_length: Longueur maximale de l'étiquette générée.
            stopwords_file: Chemin vers un fichier de mots vides à ignorer.
        """
        self.min_word_length = min_word_length
        self.max_label_length = max_label_length
        self.stopwords: Set[str] = set()
        
        # Chargement des mots vides français si disponibles
        if stopwords_file:
            try:
                with open(stopwords_file, 'r', encoding='utf-8') as f:
                    self.stopwords = set(f.read().splitlines())
            except Exception as e:
                print(f"Impossible de charger les mots vides: {e}")
        
        # Liste minimale de mots vides français
        default_stopwords = {
            "le", "la", "les", "un", "une", "des", "et", "ou", "de", "du", "en",
            "dans", "sur", "pour", "par", "avec", "sans", "est", "sont", "qui",
            "que", "quoi", "comment", "pourquoi", "quand", "où", "quel", "quelle"
        }
        self.stopwords.update(default_stopwords)
    
    def label_query(self, query: str) -> str:
        """Génère une étiquette concise pour une requête donnée.
        
        Extrait les mots significatifs de la requête en ignorant les mots vides
        et crée une étiquette représentative et de taille limitée.
        
        Args:
            query: La requête à labelliser.
            
        Returns:
            Une étiquette concise représentant la requête.
        """
        if not query:
            return ""
            
        # Nettoyage initial
        query = query.lower().strip()
        
        # Si la requête est déjà courte, la retourner telle quelle
        if len(query) <= self.max_label_length:
            return query
            
        # Tokenisation simple
        words = re.findall(r'\b\w+\b', query)
        
        # Filtrage des mots significatifs
        significant_words = [
            word for word in words 
            if len(word) >= self.min_word_length and word not in self.stopwords
        ]
        
        # Si pas de mots significatifs, utiliser le début de la requête
        if not significant_words:
            return query[:self.max_label_length - 3] + "..."
            
        # Création de l'étiquette avec les mots les plus significatifs
        label = " ".join(significant_words[:5])
        
        # Tronquer si nécessaire
        if len(label) > self.max_label_length:
            label = label[:self.max_label_length - 3] + "..."
            
        return label
        
    def aggregate_similar_queries(self, queries: List[Dict]) -> List[Dict]:
        """Agrège les requêtes similaires en utilisant leurs étiquettes.
        
        Args:
            queries: Liste de dictionnaires contenant les requêtes et leurs compteurs.
            
        Returns:
            Liste agrégée de requêtes avec leurs compteurs combinés.
        """
        labeled_queries = {}
        
        for query_item in queries:
            query = query_item["query"]
            count = query_item["count"]
            
            # Générer une étiquette pour cette requête
            label = self.label_query(query)
            
            # Agréger les compteurs pour les requêtes ayant la même étiquette
            if label in labeled_queries:
                labeled_queries[label]["count"] += count
                labeled_queries[label]["original_queries"].append(query)
            else:
                labeled_queries[label] = {
                    "count": count,
                    "original_queries": [query]
                }
        
        # Reformatage pour le retour
        result = [
            {"query": label, "count": data["count"]} 
            for label, data in labeled_queries.items()
        ]
        
        # Trier par nombre d'occurrences décroissant
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return result