# Modèles utilisés par Cléa-API

Ce document détaille les modèles de machine learning intégrés par défaut dans Cléa-API pour les différentes fonctionnalités de recherche sémantique et génération de texte.

## Résumé des modèles

| Fonctionnalité | Modèle utilisé | Lien HuggingFace |
|----------------|----------------|------------------|
| **Embeddings** | almanach/camembertav2-base | [HuggingFace](https://huggingface.co/almanach/camembertav2-base) |
| **Reranking** | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | [HuggingFace](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1) |
| **Génération LLM** | Qwen/Qwen3-0.6B | [HuggingFace](https://huggingface.co/Qwen/Qwen3-0.6B) |

## Modèle d'embeddings : CamemBERTav2

CamemBERTav2 est un modèle de langue française basé sur l'architecture DebertaV2, entraîné sur un corpus de 275 milliards de tokens de texte français. Il s'agit de la deuxième version du modèle CamemBERTa, significativement améliorée.

### Caractéristiques principales

- **Architecture** : DebertaV2 adaptée pour le français
- **Taille du corpus d'entraînement** : 275 milliards de tokens (contre ~32 milliards pour la version précédente)
- **Sources des données** : OSCAR français (projet CulturaX), documents scientifiques français (HALvest) et Wikipédia français
- **Tokenizer** : WordPiece avec 32 768 tokens, support des retours à la ligne, tabulations et emojis
- **Fenêtre de contexte** : 1 024 tokens

### Performances

Le modèle CamemBERTav2 surpasse ses prédécesseurs sur de nombreuses tâches en français :

| Modèle | UPOS | FTB-NER | CLS | PAWS-X | XNLI | FQuAD (F1) | Medical-NER |
|--------|------|---------|-----|--------|------|------------|-------------|
| CamemBERT | 97.59 | 89.97 | 94.62 | 91.36 | 81.95 | 80.98 | 70.96 |
| CamemBERTa | 97.57 | 90.33 | 94.92 | 91.67 | 82.00 | 81.15 | 71.86 |
| **CamemBERTav2** | **97.71** | **93.40** | **95.63** | **93.06** | **84.82** | **83.04** | **73.98** |

### Utilisation dans Cléa-API

Dans Cléa-API, ce modèle est utilisé pour la vectorisation des documents et des requêtes dans le module `vectordb.src.embeddings`. Il transforme les textes en vecteurs denses de grande dimension, permettant la recherche par similarité sémantique.

## Modèle de reranking : Cross-Encoder multilingue MS Marco

Il s'agit d'un modèle cross-encoder multilingue qui effectue une attention croisée entre une paire question-passage et produit un score de pertinence. Le modèle est utilisé comme reranker pour la recherche sémantique après une première étape de récupération (BM25 ou bi-encoder).

### Caractéristiques principales

- **Architecture** : Cross-Encoder basé sur mMiniLMv2-L12-H384
- **Base** : Distillé à partir de XLM-RoBERTa Large
- **Entraînement** : Fine-tuned sur le dataset MMARCO (MS Marco traduit dans 14 langues)
- **Support multilingue** : Entraîné sur 14 langues dont le français, l'anglais, l'allemand, l'espagnol, etc.
- **Utilisation** : Reranking de passages pour améliorer la précision des résultats de recherche

### Avantages du modèle multilingue

- **Compréhension multilingue** : Capacité à traiter efficacement les requêtes et documents en français et autres langues
- **Transfert de connaissances** : Bénéficie des données d'entraînement dans toutes les langues pour améliorer les performances
- **Légèreté** : Architecture compacte (L12-H384) optimisée pour des performances élevées avec des ressources limitées

## Modèle de génération (LLM) : Qwen3-0.6B

Qwen3-0.6B est un modèle de langage léger de la série Qwen3, offrant des capacités avancées de raisonnement et de génération de texte. Ce modèle est particulièrement adapté aux environnements avec ressources limitées tout en conservant des capacités de génération de qualité.

### Caractéristiques principales

- **Architecture** : Modèle causal de langage (Transformer décodeur)
- **Paramètres** : 0,6 milliard (dont 0,44 milliard hors embedding)
- **Nombre de couches** : 28
- **Têtes d'attention (GQA)** : 16 pour Q et 8 pour KV
- **Fenêtre de contexte** : 32 768 tokens
- **Modes de génération** : Support du mode "thinking" et "non-thinking"

### Modes de génération

1. **Mode thinking** (`enable_thinking=True`) :
   - Adapté aux raisonnements complexes, mathématiques, et génération de code
   - Génère un contenu de réflexion encapsulé dans un bloc `<think>...</think>` avant la réponse finale
   - Paramètres recommandés : `Temperature=0.6`, `TopP=0.95`, `TopK=20`

2. **Mode non-thinking** (`enable_thinking=False`) :
   - Optimisé pour les dialogues généraux et réponses directes
   - Paramètres recommandés : `Temperature=0.7`, `TopP=0.8`, `TopK=20`

### Utilisation dans Cléa-API

Dans Cléa-API, ce modèle est utilisé dans le module `askai` pour :
- La génération de réponses basées sur les documents retrouvés (RAG)
- Le résumé de documents
- Les réponses aux questions sur des corpus spécifiques

## Configuration des modèles

Les modèles peuvent être configurés via le fichier `.env` ou directement dans les modules correspondants :

```bash
# Configuration des modèles (dans .env)
EMBEDDING_MODEL="almanach/camembertav2-base"
CROSS_ENCODER_MODEL="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
LLM_MODEL="Qwen/Qwen3-0.6B"
```
