from sentence_transformers.cross_encoder import CrossEncoder
import os
from dotenv import load_dotenv

load_dotenv()


class ResultRanker:
    """
    @class ResultRanker
    @brief Classe responsable du réordonnancement des résultats de recherche en fonction de leur pertinence.
    """

    def __init__(self):
        """
        @brief Constructeur de la classe ResultRanker.
        Initialise le modèle Cross-Encoder utilisé pour le ranking.
        """
        self.cross_encoder_model = os.getenv(
            "CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self.model = CrossEncoder(self.cross_encoder_model)
        print(f"Modèle de ranking chargé: {self.cross_encoder_model}")

    def rank_results(self, query, results):
        """
        Classe responsable du réordonnancement des résultats de recherche en fonction de leur pertinence.

        :param query: La requête de recherche.
        :type query: str
        :param results: Liste de documents à classer.
        :type results: list[Document]
        :raises Exception: Si une erreur survient lors de la prédiction avec le Cross-Encoder.
        :return: Liste des résultats triés par pertinence.
        :rtype: list[Document]
        """
        if not results:
            return []

        print(f"Requête pour le Cross-Encoder : {query}")

        # Préparer les paires (query, document content) pour le Cross-Encoder
        pairs = []
        for result in results:
            if not isinstance(result.content, str) or not result.content.strip():
                print(f"Document avec un contenu invalide ignoré : {result.title}")
                continue
            pairs.append((query, result.content))

        if not pairs:
            print("Aucun document valide pour le ranking.")
            return []

        # Log des paires pour débogage
        print(f"Paires pour le Cross-Encoder : {pairs}")

        # Calculer les scores de similarité
        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            print(f"Erreur lors de la prédiction avec le Cross-Encoder : {e}")
            raise

        # Convertir les scores en float pour le tri
        scores = [float(score) for score in scores]

        # Associer chaque document à son score
        scored_results = list(zip(results, scores))

        # Trier par score décroissant
        sorted_results = sorted(scored_results, key=lambda x: x[1], reverse=True)

        # Retourner seulement les documents, maintenant triés
        return [result for result, _ in sorted_results]
