from sqlalchemy.orm import Session
from .database import Document
from .embeddings import EmbeddingGenerator
from .ranking import ResultRanker
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
import json 


class DocumentSearchResponse(BaseModel):
    """
    @brief Classe représentant un document de recherche.
    @details Contient les informations du document ainsi que les métadonnées.
    @structure:
        - id (int): ID du document.
        - title (str): Titre du document.
        - content (str): Contenu du document.
        - theme (str): Thème du document.
        - document_type (str): Type de document.
        - publish_date (date): Date de publication.
        - metadata (dict): Métadonnées associées au document.
    """
    id: int
    title: str
    content: str
    theme: str
    document_type: str
    publish_date: date
    metadata: dict
    
class DocumentSearchRequest(BaseModel):
    """
    @brief Classe représentant une requête de recherche.
    @details Contient la requête de recherche, le nombre de résultats souhaités et les filtres optionnels.
    @structure:
        - query (str): La requête de recherche.
        - top_k (int): Nombre de résultats à retourner.
        - theme (str, optional): Thème du document.
        - document_type (str, optional): Type de document.
        - start_date (date, optional): Date de début pour le filtrage.
        - end_date (date, optional): Date de fin pour le filtrage.
    """
    query: str
    top_k: int = 10
    theme: Optional[str] = None
    document_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class SearchResults(BaseModel):
    """_summary_
    @brief Classe représentant les résultats de recherche.
    @details Contient la requête, les filtres appliqués, le nombre total de résultats et les résultats eux-mêmes.
    @structure:
        - query (str): La requête de recherche.
        - filters (dict): Les filtres appliqués lors de la recherche.
        - total_results (int): Le nombre total de résultats trouvés.
        - results (List[DocumentSearchResponse]): Liste des résultats de recherche formatés.
    """
    query: str
    filters: Optional[dict]
    total_results: int
    results: List[DocumentSearchResponse]
       
class SearchEngine:
    """
    @class SearchEngine
    @brief Classe principale pour effectuer des recherches hybrides combinant filtrage par métadonnées et recherche vectorielle.
    """

    def __init__(self):
        """
        @brief Constructeur de la classe SearchEngine.
        Initialise les composants nécessaires pour la recherche.
        """
        self.embedding_generator = EmbeddingGenerator()
        self.ranker = ResultRanker()
    
    def search(self, db: Session, query: str, filters=None, top_k=10) -> List[DocumentSearchResponse]:
        """
        Recherche hybride combinant filtrage par métadonnées et recherche vectorielle.
        """
        query_str = query
        # Étape 1: Générer l'embedding de la requête
        query_embedding = self.embedding_generator.generate_embedding(query)
        print(f"length Embedding de la requête : {len(query_embedding)}")

        # Étape 2: Appliquer les filtres avec SQLAlchemy ORM
        query = db.query(Document)
        if filters:
            if filters.get("theme"):
                query = query.filter(Document.theme == filters["theme"])
            if filters.get("document_type"):
                query = query.filter(Document.document_type == filters["document_type"])
            if filters.get("start_date") and filters.get("end_date"):
                query = query.filter(Document.publish_date.between(filters["start_date"], filters["end_date"]))

        filtered_results = query.all()
        print(f"Documents filtrés : {[doc.title for doc in filtered_results]}")

        # Étape 3: Récupérer les embeddings pour les résultats filtrés
        document_ids = [doc.id for doc in filtered_results]
        if not document_ids:
            print("Aucun document filtré trouvé.")
            return []

        document_embeddings = {
            str(doc.id): json.loads(doc.embedding) if doc.embedding else None
            for doc in filtered_results
        }
        print(f"Length Embeddings des documents : {len(document_embeddings)}")

        # Étape 4: Calculer les similitudes vectorielles
        scored_documents = []
        for doc in filtered_results:
            doc_embedding = document_embeddings.get(str(doc.id))
            if not doc_embedding:
                print(f"Pas d'embedding pour le document {doc.title}")
                continue

            similarity = self.embedding_generator.compute_similarity(query_embedding, doc_embedding)
            scored_documents.append((doc, similarity))
            print(f"Similarité pour {doc.title} : {similarity}")
            

        # Ajouter les métadonnées aux documents
        for doc, similarity in scored_documents:
            if not hasattr(doc, "custom_metadata"):
                doc.custom_metadata = {}
            doc.custom_metadata["similarity_score"] = similarity
            
        # Trier par score de similarité
        vector_results = sorted(scored_documents, key=lambda x: x[1], reverse=True)[:top_k * 2]
        vector_documents = [doc for doc, _ in vector_results]
        print(f"Documents triés par similarité --> Titre: \n{[doc.title for doc in vector_documents]}\n") 
        valid_documents = []
        for doc in vector_documents:
            if not isinstance(doc.content, str) or not doc.content.strip():
                print(f"Document avec un contenu invalide ignoré : {doc.title}")
                continue
            valid_documents.append(doc)

        if not valid_documents:
            print("Aucun document valide pour le reranking.")
            return []

        print(f"Documents valides pour le reranking : {[doc.title for doc in valid_documents]}")
        # Étape 5: Reranking avec le Cross-Encoder  
        ranked_results = self.ranker.rank_results(query_str, valid_documents)
        print(f"Documents après reranking : {[doc.title for doc in ranked_results]}")
        # Étape 6: Limiter le nombre de résultats
        ranked_results = ranked_results[:top_k]
        print(f"Résultats finaux : {[doc.title for doc in ranked_results]}")
        # Étape 7: Formater les résultats
        formatted_results = self.format_results(query_str, ranked_results, filters)
        return formatted_results
    
    def hybrid_search(self, db: Session, query: str, filters=None, top_k=10) -> SearchResults:
        """
        @brief Méthode principale exposée pour la recherche hybride.
        @param db Session de base de données.
        @param query Texte de la requête.
        @param filters Filtres sur les métadonnées (date, thème, type).
        @param top_k Nombre de résultats à retourner.
        @return Liste des documents les plus pertinents avec leurs métadonnées.
        """
        # Déléguer la recherche à la méthode interne
        results = self.search(db, query, filters, top_k)

        # Construire l'objet SearchResults
        return SearchResults(
            query=query,
            filters=filters if filters else None,
            total_results=len(results),
            results=results
        )

    def format_results(self, query: str, results: List[Document], filters: dict = None) -> List[DocumentSearchResponse]:
        """
        Formate les résultats de recherche avant de les renvoyer au frontend.

        Args:
            query (str): La requête de recherche.
            results (list[Document]): Liste des résultats de recherche.
            filters (dict, optional): Filtres appliqués lors de la recherche.

        Returns:
            List[DocumentSearchResponse]: Résultats formatés avec le contexte de la recherche et les métadonnées.
        """
        return [
            DocumentSearchResponse(
                id=result.id,
                title=result.title,
                content=result.content[:200] + "..." if len(result.content) > 200 else result.content,
                theme=result.theme,
                document_type=result.document_type,
                publish_date=result.publish_date,
                metadata={
                    "similarity_score": result.custom_metadata.get("similarity_score", "Non disponible") if hasattr(result, "custom_metadata") else "Non disponible",
                    "rank": index + 1
                }
            )
            for index, result in enumerate(results)
        ]