from pydantic import BaseModel
from typing import Dict, Any


class PromptTemplate(BaseModel):
    """
    Modèle de base pour les templates de prompts.

    Attributes:
        template (str): Template de texte avec placeholders.
        variables (Dict[str, Any]): Variables pour remplacer les placeholders.
    """

    template: str
    variables: Dict[str, Any] = {}

    def format(self) -> str:
        """
        Formate le template en remplaçant les placeholders.

        Returns:
            Template formaté avec variables substituées.
        """
        return self.template.format(**self.variables)


class StandardRAGPrompt(PromptTemplate):
    """
    Prompt standard pour les tâches RAG simples.

    Ce template est optimisé pour les cas d'usage courants où une
    réponse directe basée sur le contexte est attendue.
    """

    template: str = """Tu es un assistant spécialisé dans la recherche documentaire qui répond aux questions à partir du contexte fourni.

QUESTION: {query}

CONTEXTE:
{context}

INSTRUCTIONS:
1. Réponds UNIQUEMENT en utilisant les informations du CONTEXTE ci-dessus.
2. Si le CONTEXTE ne contient pas l'information nécessaire, indique clairement que tu ne peux pas répondre à cette question.
3. Cite les sources pertinentes dans ta réponse.
4. Sois concis et précis.
5. Concentre-toi uniquement sur les éléments du CONTEXTE qui répondent directement à la QUESTION.

RÉPONSE:
"""


class SummaryRAGPrompt(PromptTemplate):
    """
    Prompt pour les tâches de résumé de documents.

    Ce template guide le modèle pour produire un résumé structuré
    basé sur plusieurs documents.
    """

    template: str = """Tu es un assistant spécialisé dans la synthèse de documents.

DOCUMENTS:
{context}

INSTRUCTIONS:
1. Produis un résumé concis et structuré des documents fournis.
2. Organise l'information par thèmes ou points clés.
3. Limite-toi UNIQUEMENT au contenu des documents.
4. Identifie les points communs et les divergences entre les documents.
5. Sois factuel et objectif.

Longueur cible: environ {target_length} mots.

RÉSUMÉ:
"""


class ComparisonRAGPrompt(PromptTemplate):
    """
    Prompt pour comparer des éléments à partir de documents.

    Ce template est conçu pour aider le modèle à analyser et comparer
    des éléments distincts mentionnés dans le contexte.
    """

    template: str = """Tu es un assistant spécialisé dans l'analyse comparative.

QUESTION: {query}

CONTEXTE:
{context}

INSTRUCTIONS:
1. Compare les éléments mentionnés dans la question selon les informations du CONTEXTE.
2. Structure ta réponse sous forme de tableau comparatif avec les critères pertinents.
3. Utilise UNIQUEMENT les informations du CONTEXTE.
4. Si certaines informations manquent, indique-le clairement.

TABLEAU COMPARATIF:
"""
