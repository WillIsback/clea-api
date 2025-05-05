# Module **rag** (Retrieval-Augmented Generation)

Ce module implémente un processeur RAG optimisé pour petits LLM qui combine recherche vectorielle et génération de réponses via Qwen3. Il inclut une gestion avancée du raisonnement et du contexte pour une transparence maximale.

---

## Table des matières

1. Installation
2. Modèles (schemas)
3. Classe `RAGProcessor`
   * Constructeur
   * Méthode `format_context`
   * Méthode `get_prompt_template`
   * Méthode `retrieve_documents`
   * Méthode `retrieve_and_generate`
   * Méthode `retrieve_and_generate_stream`
4. Classe `ModelLoader`
   * Constructeur
   * Méthode `load`
   * Méthode `generate`
   * Méthode `generate_with_thinking`
5. Classe `AsyncStreamedResponse`
   * Méthode `generate_stream`
6. Mode Thinking & Contexte
7. Exemple d'utilisation

---

## Installation

```bash
# Installer les dépendances
uv pip install -r requirements.txt

# Prérequis pour les modèles Qwen3
uv pip install protobuf tokenizers>=0.13.3
```

---

## Modèles (schemas)

Les templates de prompts utilisés par le processeur RAG se trouvent dans prompt_schemas.py :

* **`PromptTemplate`** : modèle de base pour les templates de prompts.
* **`StandardRAGPrompt`** : prompt optimisé pour les requêtes RAG simples.
* **`SummaryRAGPrompt`** : prompt pour les tâches de résumé de documents.
* **`ComparisonRAGPrompt`** : prompt pour comparer des éléments à partir des documents.

> Pour plus de détails sur ces schémas, consultez le fichier source prompt_schemas.py.

---

## Classe `RAGProcessor`

### Constructeur

```python
processor = RAGProcessor(
    model_loader: ModelLoader,
    search_engine: SearchEngine,
    db_session: Session,
    max_tokens_per_doc: int = 300,
    max_docs: int = 5,
)
```

* **Initialise** :
  * `model_loader` : chargeur de modèle LLM
  * `search_engine` : moteur de recherche vectorielle
  * `db_session` : session de base de données SQLAlchemy
  * `max_tokens_per_doc` : nombre maximum de tokens par document
  * `max_docs` : nombre maximum de documents à utiliser

### Méthode `format_context`

```python
def format_context(self, search_results: SearchResponse) -> str:
    """Formate les résultats de recherche en contexte structuré pour le LLM.
    
    Utilise les résultats d'une requête pour créer un contexte formaté
    qui sera utilisé dans le prompt envoyé au modèle LLM.
    
    Args:
        search_results: Réponse de recherche contenant les chunks pertinents.
        
    Returns:
        str: Contexte formaté prêt à être injecté dans le prompt.
    """
    ...
```

* **But** : formater les résultats de recherche en contexte structuré pour le LLM
* **Arguments** :
  * `search_results`: réponse de recherche contenant les chunks pertinents
* **Fonctionnement** :
  1. Itère sur chaque résultat et crée une représentation structurée
  2. Inclut les métadonnées: titre, source, thème, date
  3. Ajoute le contexte hiérarchique si disponible (sections parentes)
  4. Indique le score de pertinence
* **Retour** : chaîne de caractères formatée pour injecter dans le prompt

### Méthode `get_prompt_template`

```python
def get_prompt_template(
    self, 
    query: str, 
    context: str, 
    prompt_type: str = "standard", 
    **kwargs
) -> PromptTemplate:
    """Retourne un template de prompt adapté au type de requête.
    
    Args:
        query: Question de l'utilisateur.
        context: Contexte documentaire formaté.
        prompt_type: Type de prompt à utiliser ('standard', 'summary', 'comparison').
        **kwargs: Paramètres additionnels spécifiques au type de prompt.
        
    Returns:
        PromptTemplate: Template de prompt configuré avec les variables appropriées.
        
    Raises:
        ValueError: Si le type de prompt spécifié n'est pas reconnu.
    """
    ...
```

* **But** : créer un template de prompt adapté au type de requête
* **Arguments** :
  * `query` : question de l'utilisateur
  * `context` : contexte documentaire formaté
  * `prompt_type` : type de prompt ('standard', 'summary', 'comparison')
  * `**kwargs` : paramètres additionnels spécifiques au type de prompt
* **Types disponibles** :
  * `standard` : prompt pour questions/réponses génériques
  * `summary` : prompt pour résumé de documents
  * `comparison` : prompt pour analyse comparative
* **Retour** : instance de `PromptTemplate` configurée

### Méthode `retrieve_documents`

```python
async def retrieve_documents(
    self, 
    query: str, 
    filters: Dict[str, Any] = None
) -> SearchResponse:
    """Récupère les documents pertinents pour une requête donnée.
    
    Effectue une recherche dans la base de données vectorielle et retourne
    les résultats formatés selon le schéma standard de l'application.
    
    Args:
        query: Question de l'utilisateur.
        filters: Filtres à appliquer lors de la recherche.
            
    Returns:
        SearchResponse: Réponse contenant les résultats de recherche pertinents.
    """
    ...
```

* **But** : récupérer les documents pertinents pour une requête donnée
* **Arguments** :
  * `query` : question de l'utilisateur
  * `filters` : filtres à appliquer lors de la recherche
* **Fonctionnement** :
  1. Construit une requête `SearchRequest` avec les paramètres fournis
  2. Exécute la recherche via `search_engine.hybrid_search`
  3. Journalise le nombre de documents récupérés
* **Retour** : réponse de recherche (`SearchResponse`) contenant les documents pertinents

### Méthode `retrieve_and_generate`

```python
async def retrieve_and_generate(
    self, 
    query: str, 
    filters: Dict[str, Any] = None,
    prompt_type: str = "standard",
    generation_kwargs: Dict[str, Any] = None,
    enable_thinking: Optional[bool] = None,
    **prompt_kwargs
) -> tuple:
    """Récupère les documents pertinents et génère une réponse.
    
    Args:
        query: Question de l'utilisateur.
        filters: Filtres à appliquer lors de la recherche.
        prompt_type: Type de prompt à utiliser ('standard', 'summary', 'comparison').
        generation_kwargs: Paramètres additionnels pour la génération de texte.
        enable_thinking: Active ou désactive le mode de réflexion. Si None, utilise la configuration du modèle.
        **prompt_kwargs: Paramètres additionnels pour le template de prompt.
        
    Returns:
        tuple: 
            - Si enable_thinking=True : (thinking, response, search_results)
            - Si enable_thinking=False : (response, search_results)
    """
    ...
```

* **But** : récupérer les documents pertinents et générer une réponse complète
* **Arguments** :
  * `query` : question de l'utilisateur
  * `filters` : filtres à appliquer lors de la recherche
  * `prompt_type` : type de prompt à utiliser
  * `generation_kwargs` : paramètres pour la génération de texte
  * `enable_thinking` : active le mode de réflexion du modèle
  * `**prompt_kwargs` : paramètres additionnels pour le template de prompt
* **Fonctionnement** :
  1. Récupère les documents pertinents via `retrieve_documents`
  2. Formate le contexte documentaire avec `format_context`
  3. Crée le prompt avec le template approprié
  4. Génère la réponse avec le modèle LLM
* **Retour** : 
  * Avec `enable_thinking=True` : tuple (thinking, response, search_results)
  * Avec `enable_thinking=False` : tuple (response, search_results)

### Méthode `retrieve_and_generate_stream`

```python
async def retrieve_and_generate_stream(
    self,
    query: str,
    filters: Dict[str, Any] = None,
    prompt_type: str = "standard",
    generation_kwargs: Dict[str, Any] = None,
    enable_thinking: Optional[bool] = None,
    **prompt_kwargs
) -> AsyncGenerator[Dict[str, Any], None]:
    """Récupère les documents pertinents et génère une réponse en streaming.
    
    Cette méthode enrichit la réponse avec les documents utilisés pour la génération.
    Chaque fragment retourné est un dictionnaire identifiant son type et contenu.
    
    Args:
        query: Question de l'utilisateur.
        filters: Filtres à appliquer lors de la recherche.
        prompt_type: Type de prompt à utiliser ('standard', 'summary', 'comparison').
        generation_kwargs: Paramètres additionnels pour la génération de texte.
        enable_thinking: Active ou désactive le mode de réflexion. Si None, utilise la configuration du modèle.
        **prompt_kwargs: Paramètres additionnels pour le template de prompt.
        
    Yields:
        Dict[str, Any]: Fragments de la réponse ou métadonnées avec leur type :
            - {"type": "thinking", "content": str} pour les parties de réflexion
            - {"type": "response", "content": str} pour les parties de réponse
            - {"type": "context", "content": Dict} pour le contexte utilisé
            - {"type": "error", "content": str} en cas d'erreur
            - {"type": "done", "content": ""} à la fin du streaming
    """
    ...
```

* **But** : récupérer les documents et générer une réponse en streaming (progressive)
* **Arguments** : identiques à `retrieve_and_generate`
* **Fonctionnement** :
  1. Récupère et formate les documents comme `retrieve_and_generate`
  2. Transmet immédiatement le contexte au client (`{"type": "context", "content": search_results.dict()}`)
  3. Utilise `AsyncStreamedResponse` pour générer la réponse progressivement
  4. Émet chaque fragment selon son type (réponse, réflexion, contexte)
  5. Signale la fin du streaming avec un événement `{"type": "done"}`
* **Retour** : générateur asynchrone de fragments typés

---

## Classe `ModelLoader`

### Constructeur

```python
loader = ModelLoader(
    model_name: str = "Qwen/Qwen3-0.6B",
    device: Optional[str] = None,
    load_in_8bit: bool = False,
    base_path: str = "askai/models",
    thinking_enabled: bool = True,
    auto_load: bool = False,
    test_mode: bool = False,
    auto_fix: bool = True
)
```

* **But** : gérer le chargement et la configuration des modèles LLM
* **Arguments** :
  * `model_name` : nom du modèle à charger (Qwen/Qwen3-0.6B, Qwen/Qwen3-1.7B)
  * `device` : périphérique de calcul ('cpu', 'cuda', 'auto')
  * `load_in_8bit` : active la quantification 8-bit
  * `base_path` : chemin vers le répertoire des modèles
  * `thinking_enabled` : active le mode de réflexion par défaut
  * `auto_load` : charge automatiquement le modèle à l'initialisation
  * `test_mode` : active un mode de simulation sans charger de modèle

### Méthode `load`

```python
def load(self) -> None:
    """Charge le modèle et le tokenizer en mémoire.
    
    Vérifie si le mode test est activé, puis charge le tokenizer et le modèle
    depuis HuggingFace ou en local, et configure les options d'optimisation.
    
    Raises:
        RuntimeError: Si le chargement échoue.
    """
    ...
```

* **But** : charger le modèle et le tokenizer en mémoire
* **Fonctionnement** :
  1. Vérifie si le mode test est activé
  2. Charge le tokenizer et le modèle depuis HuggingFace ou local
  3. Configure les options de quantification et d'optimisation
* **Raises** : `RuntimeError` si le chargement échoue

### Méthode `generate`

```python
def generate(
    self,
    prompt: str,
    enable_thinking: bool = True,
    max_new_tokens: int = 2048,
    do_sample: bool = True,
    temperature: float = 0.6,
    top_p: float = 0.95,
    top_k: int = 20,
    **kwargs
) -> str:
    """Génère du texte à partir d'un prompt donné.
    
    Args:
        prompt: Texte d'entrée pour la génération.
        enable_thinking: Active le mode de réflexion.
        max_new_tokens: Nombre maximum de tokens à générer.
        do_sample: Utilise l'échantillonnage pour la génération.
        temperature: Contrôle la créativité (plus élevé = plus aléatoire).
        top_p: Filtrage nucleus sampling.
        top_k: Nombre de tokens considérés à chaque étape.
        **kwargs: Paramètres additionnels pour la génération.
        
    Returns:
        str: Texte généré par le modèle.
    """
    ...
```

* **But** : générer du texte à partir d'un prompt donné
* **Arguments** :
  * `prompt` : texte d'entrée pour la génération
  * `enable_thinking` : active le mode de réflexion
  * `max_new_tokens` : nombre maximum de tokens à générer
  * `do_sample` : utilise l'échantillonnage pour la génération
  * `temperature` : contrôle la créativité (plus élevé = plus aléatoire)
  * `top_p` : filtrage nucleus sampling
  * `top_k` : nombre de tokens considérés à chaque étape
* **Retour** : texte généré par le modèle

### Méthode `generate_with_thinking`

```python
def generate_with_thinking(
    self,
    prompt: str,
    max_new_tokens: int = 2048,
    do_sample: bool = True,
    temperature: float = 0.6,
    **kwargs
) -> Tuple[str, str]:
    """Génère du texte avec séparation explicite entre réflexion et réponse.
    
    Cette méthode capture le raisonnement étape par étape du modèle et le sépare
    de la réponse finale grâce à des balises spécifiques dans le prompt.
    
    Args:
        prompt: Texte d'entrée pour la génération.
        max_new_tokens: Nombre maximum de tokens à générer.
        do_sample: Utilise l'échantillonnage pour la génération.
        temperature: Contrôle la créativité (plus élevé = plus aléatoire).
        **kwargs: Paramètres additionnels pour la génération.
        
    Returns:
        Tuple[str, str]: Tuple contenant (réflexion, réponse).
    """
    ...
```

* **But** : générer du texte avec séparation entre réflexion et réponse finale
* **Arguments** : similaires à `generate`
* **Fonctionnement** :
  1. Ajoute des instructions au modèle pour séparer réflexion et réponse
  2. Utilise des balises spéciales (`<thinking>`, `</thinking>`, `<answer>`) dans le prompt
  3. Extrait et sépare la partie réflexion de la partie réponse
* **Retour** : tuple (`thinking`, `answer`) contenant le raisonnement et la réponse

---

## Classe `AsyncStreamedResponse`

### Constructeur

```python
streamer = AsyncStreamedResponse(
    model_loader: ModelLoader,
    filter_thinking: bool = False
)
```

* **But** : gérer les réponses en streaming pour les interactions avec le LLM
* **Arguments** :
  * `model_loader` : chargeur de modèle LLM
  * `filter_thinking` : si True, filtre le contenu de réflexion des réponses

### Méthode `generate_stream`

```python
async def generate_stream(
    self,
    prompt: str,
    enable_thinking: bool = True,
    chunk_size: int = 3,
    **kwargs
) -> AsyncGenerator[Dict[str, Any], None]:
    """Génère une réponse en streaming progressif avec différenciation des types.
    
    Args:
        prompt: Texte d'entrée pour la génération.
        enable_thinking: Active le mode de réflexion.
        chunk_size: Nombre de mots par fragment en mode simulation.
        **kwargs: Paramètres additionnels pour la génération.
        
    Yields:
        Dict[str, Any]: Fragments typés de la génération:
            - {"type": "thinking", "content": str} pour les parties de réflexion
            - {"type": "response", "content": str} pour les parties de réponse
    """
    ...
```

* **But** : générer une réponse en streaming progressif avec différenciation des types
* **Arguments** :
  * `prompt` : texte d'entrée pour la génération
  * `enable_thinking` : active le mode de réflexion
  * `chunk_size` : nombre de mots par fragment en mode simulation
  * `**kwargs` : paramètres additionnels pour la génération
* **Fonctionnement** :
  1. Détecte si le modèle supporte nativement le streaming
  2. Si oui, utilise le streaming natif du modèle
  3. Sinon, simule le streaming par découpage progressif
  4. Identifie et type chaque fragment (réflexion ou réponse)
* **Retour** : générateur asynchrone de fragments typés

---

## Mode Thinking & Contexte

Le module RAG implémente une approche transparente qui permet aux utilisateurs d'accéder:

1. Au **raisonnement complet** du modèle (mode "thinking")
2. Au **contexte documentaire** utilisé pour générer la réponse

### Raisonnement (Thinking)

Le mode thinking permet de visualiser:

* Le processus de réflexion étape par étape du modèle
* L'analyse des documents fournis
* Le raisonnement pour arriver à la conclusion
* Les références explicites aux sources

#### Exemple d'activation:

```python
# Mode normal
response, search_results = await rag_processor.retrieve_and_generate(
    query="Comment réduire les émissions de CO2?",
    enable_thinking=False
)

# Mode avec raisonnement visible
thinking, response, search_results = await rag_processor.retrieve_and_generate(
    query="Comment réduire les émissions de CO2?",
    enable_thinking=True
)

print("Raisonnement du modèle:")
print(thinking)
```

### Contexte documentaire

Le contexte documentaire permet à l'utilisateur de:

* Vérifier les sources utilisées pour générer la réponse
* Évaluer la pertinence des documents récupérés
* Accéder aux métadonnées complètes (source, date, score)
* Explorer le contexte hiérarchique (sections parentes)

#### Exploitation du contexte:

```python
# Récupération de la réponse et du contexte
response, search_results = await rag_processor.retrieve_and_generate(
    query="Quelles sont les réglementations sur l'isolation thermique?",
    enable_thinking=False
)

# Affichage des sources utilisées
print(f"Réponse basée sur {len(search_results.results)} source(s):")
for i, result in enumerate(search_results.results):
    print(f"{i+1}. {result.title} (score: {result.score:.2f})")
    print(f"   Thème: {result.theme}, Type: {result.document_type}")
    print(f"   Date: {result.publish_date}")
    print(f"   Extrait: {result.content[:100]}...")
```

### Streaming avec types différenciés

En mode streaming, chaque fragment émis est typé pour permettre:

* L'affichage différencié du raisonnement et de la réponse
* L'accès immédiat au contexte dès sa récupération
* La mise en forme adaptée selon le type dans l'interface

```python
async for chunk in rag_processor.retrieve_and_generate_stream(
    query="Expliquez les normes de sécurité incendie",
    enable_thinking=True
):
    if chunk["type"] == "context":
        # Afficher les sources dans l'interface
        display_sources(chunk["content"]["results"])
    elif chunk["type"] == "thinking":
        # Afficher en italique gris dans une zone dédiée
        append_to_thinking_area(chunk["content"])
    elif chunk["type"] == "response":
        # Afficher en texte normal dans la zone de réponse
        append_to_response_area(chunk["content"])
```

---

## Exemple d'utilisation

```python
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from vectordb.src.search import SearchEngine
from askai.src.model_loader import ModelLoader
from askai.src.rag import RAGProcessor

# Fonction asynchrone principale
async def main():
    # 1. Préparer la session de base de données
    engine_db = create_engine("postgresql://user:password@localhost/clea")
    SessionLocal = sessionmaker(bind=engine_db)
    db = SessionLocal()
    
    # 2. Initialiser le moteur de recherche
    search_engine = SearchEngine()
    
    # 3. Initialiser le chargeur de modèle (en mode test pour la démo)
    model_loader = ModelLoader(
        model_name="Qwen/Qwen3-0.6B",
        test_mode=True,  # Remplacer par False en production
        thinking_enabled=True
    )
    
    # 4. Créer le processeur RAG
    rag_processor = RAGProcessor(
        model_loader=model_loader,
        search_engine=search_engine,
        db_session=db,
        max_docs=5
    )
    
    # 5. Exemple de requête avec génération complète et accès au raisonnement
    query = "Comment réduire l'empreinte carbone d'une entreprise industrielle?"
    filters = {"theme": "RSE", "normalize_scores": True}
    
    thinking, response, search_results = await rag_processor.retrieve_and_generate(
        query=query,
        filters=filters,
        prompt_type="standard",
        enable_thinking=True
    )
    
    # Afficher la réponse
    print(f"Réponse finale:\n{response}")
    
    # Afficher le raisonnement si nécessaire
    print("\nRaisonnement du modèle:")
    print(thinking)
    
    # Afficher les sources utilisées
    print("\nSources utilisées:")
    for i, result in enumerate(search_results.results):
        print(f"{i+1}. {result.title} (score: {result.score:.2f})")
    
    # 6. Exemple de requête avec génération en streaming typé
    print("\nGénération en streaming avec types:")
    
    # Conteneurs pour collecter différents types de contenu
    thinking_content = []
    response_content = []
    context = None
    
    async for chunk in rag_processor.retrieve_and_generate_stream(
        query="Quelles sont les meilleures pratiques de gestion des déchets?",
        filters={"theme": "Environnement"},
        enable_thinking=True
    ):
        if chunk["type"] == "thinking":
            thinking_content.append(chunk["content"])
            print("[Thinking] ", chunk["content"], end="")
        elif chunk["type"] == "response":
            response_content.append(chunk["content"])
            print("[Réponse] ", chunk["content"], end="")
        elif chunk["type"] == "context":
            context = chunk["content"]
            print(f"\n[Contexte récupéré: {len(context['results'])} documents]")
        elif chunk["type"] == "done":
            print("\n[Génération terminée]")

# Exécuter la fonction asynchrone
if __name__ == "__main__":
    asyncio.run(main())
```

### Exemple avec interface FastAPI

```python
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, Optional, List
import json

from askai.src.model_loader import ModelLoader
from askai.src.rag import RAGProcessor
from vectordb.src.search import SearchEngine
from vectordb.src.database import get_db

app = FastAPI()

# Singleton pour le modèle (partagé entre requêtes)
model_loader = ModelLoader(
    model_name="Qwen/Qwen3-0.6B",
    auto_load=True,  # Charge le modèle au démarrage
    thinking_enabled=True
)
search_engine = SearchEngine()

@app.post("/askai/query")
async def query(
    question: str,
    theme: Optional[str] = None,
    enable_thinking: bool = False,
    db: Session = Depends(get_db)
):
    # Créer un processeur RAG pour cette requête
    rag_processor = RAGProcessor(
        model_loader=model_loader,
        search_engine=search_engine,
        db_session=db
    )
    
    # Générer la réponse avec ou sans raisonnement
    if enable_thinking:
        thinking, response, search_results = await rag_processor.retrieve_and_generate(
            query=question,
            filters={"theme": theme} if theme else {},
            enable_thinking=True
        )
        # Retourner à la fois la réponse, le raisonnement et les sources
        return {
            "question": question,
            "answer": response,
            "thinking": thinking,
            "sources": [
                {
                    "title": result.title,
                    "theme": result.theme,
                    "document_type": result.document_type,
                    "publish_date": result.publish_date,
                    "score": result.score
                }
                for result in search_results.results
            ]
        }
    else:
        # Version sans raisonnement
        response, search_results = await rag_processor.retrieve_and_generate(
            query=question,
            filters={"theme": theme} if theme else {},
            enable_thinking=False
        )
        return {
            "question": question,
            "answer": response,
            "sources": [
                {
                    "title": result.title,
                    "score": result.score
                }
                for result in search_results.results
            ]
        }

@app.websocket("/askai/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    
    # Recevoir la requête initiale
    data = await websocket.receive_text()
    request = json.loads(data)
    
    # Créer un processeur RAG
    rag_processor = RAGProcessor(
        model_loader=model_loader,
        search_engine=search_engine,
        db_session=db
    )
    
    # Transmettre les fragments typés via le WebSocket
    async for chunk in rag_processor.retrieve_and_generate_stream(
        query=request["question"],
        filters={"theme": request.get("theme")} if "theme" in request else {},
        enable_thinking=request.get("enable_thinking", False)
    ):
        await websocket.send_json(chunk)
```

---

> **Voir aussi** : les **endpoints** FastAPI dans `askai_endpoint.py`
> – `POST /askai/query` → génère une réponse complète avec raisonnement et contexte optionnels
