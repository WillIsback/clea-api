# Cléa-API

Cléa-API est un framework conçu pour le chargement de documents et la recherche hybride combinant la recherche vectorielle et basée sur les métadonnées. Il fournit des fonctionnalités CRUD pour gérer les documents et des endpoints pour effectuer des recherches avancées.

---

## **Caractéristiques principales**

- **Chargement de documents** : Extraction et traitement de documents dans divers formats (PDF, Word, JSON, etc.).
- **Recherche hybride** : Combinaison de la recherche vectorielle et basée sur les métadonnées.
- **Gestion des documents** : CRUD complet pour les documents.
- **Extensibilité** : Architecture modulaire pour ajouter facilement de nouvelles fonctionnalités.
- **Support de PostgreSQL avec pgvector** : Stockage et recherche vectorielle optimisés.

---

## **Structure du projet**

```shell
.
├── clea_doc_loader       # Module pour le chargement et l'extraction de documents
│   ├── api               # Endpoints pour le chargement de documents
│   ├── src               # Logique métier pour l'extraction de documents
│   └── test              # Tests unitaires pour le module
├── clea_pipeline         # Module pour le traitement des documents
│   ├── api               # Endpoints pour le traitement des documents
│   ├── src               # Logique métier pour le pipeline de traitement
│   └── test              # Tests unitaires pour le module
├── clea_vectordb         # Module pour la gestion des documents et la recherche
│   ├── api               # Endpoints pour la gestion et la recherche
│   ├── src               # Logique métier pour la base de données et la recherche
│   └── test              # Tests unitaires pour le module
├── demo                  # Fichiers de démonstration pour tester les fonctionnalités
├── main.py               # Point d'entrée principal de l'application
├── pyproject.toml        # Configuration du projet Python
├── requirements.txt      # Liste des dépendances Python
├── Dockerfile            # Fichier Docker pour le déploiement
├── start.sh              # Script pour démarrer l'application
└── README.md             # Documentation du projet
```

---

## **Installation**

### **Prérequis**

- **Python 3.11 ou supérieur**
- **PostgreSQL** avec l'extension `pgvector`
- **WSL (Windows Subsystem for Linux)** avec OpenSUSE Tumbleweed (si applicable)

### **Étapes d'installation**

1. **Cloner le dépôt**

   ```bash
   git clone https://github.com/votre-repo/clea-api.git
   cd clea-api
   ```

2. **Installer les dépendances**

   Utilisez le gestionnaire de paquets `uv` pour installer les dépendances :

   ```bash
   uv pip install -r requirements.txt
   ```

3. **Configurer les variables d'environnement**

   Créez un fichier .env à la racine du projet et configurez les variables suivantes :

   ```env
   DB_USER=postgres
   DB_PASSWORD=your_password
   DB_NAME=clea_db
   DB_HOST=localhost
   DB_PORT=5432
   API_HOST=localhost
   API_PORT=8080
   ```

4. **Initialiser la base de données**

   Lancez le script d'initialisation de la base de données :

   ```bash
   uv python main.py
   ```

5. **Démarrer l'application**

   Utilisez le script start.sh pour démarrer l'API :

   ```bash
   ./start.sh
   ```

   L'API sera disponible à l'adresse suivante : [http://localhost:8080](http://localhost:8080).

---

## **Utilisation**

### **Endpoints principaux**

#### **1. Chargement de documents**

- **Endpoint** : `/doc_loader/upload-file`
- **Méthode** : `POST`
- **Description** : Charge un fichier et extrait son contenu.
- **Exemple de requête** :

  ```bash
  curl -X POST "http://localhost:8080/doc_loader/upload-file" \
       -F "file=@demo/demo.txt" \
       -F "max_length=1000" \
       -F "theme=Test"
  ```

#### **2. Traitement des documents**

- **Endpoint** : `/pipeline/process-and-store`
- **Méthode** : `POST`
- **Description** : Traite un fichier et l'insère dans la base de données.
- **Exemple de requête** :

  ```bash
  curl -X POST "http://localhost:8080/pipeline/process-and-store" \
       -F "file=@demo/demo.txt" \
       -F "max_length=1000" \
       -F "theme=Test"
  ```

#### **3. Gestion des documents**

- **Endpoint** : `/database/add_document`
- **Méthode** : `POST`
- **Description** : Ajoute un document à la base de données.
- **Exemple de requête** :

  ```bash
  curl -X POST "http://localhost:8080/database/add_document" \
       -H "Content-Type: application/json" \
       -d '[
             {
               "title": "Document de test",
               "content": "Ceci est un document de test.",
               "theme": "Test",
               "document_type": "TXT",
               "publish_date": "2025-01-01"
             }
           ]'
  ```

#### **4. Recherche hybride**

- **Endpoint** : `/search/hybrid_search`
- **Méthode** : `POST`
- **Description** : Recherche des documents en combinant la recherche vectorielle et basée sur les métadonnées.
- **Exemple de requête** :

  ```bash
  curl -X POST "http://localhost:8080/search/hybrid_search" \
       -H "Content-Type: application/json" \
       -d '{
             "query": "exemple",
             "theme": "Test",
             "top_k": 5
           }'
  ```

---

## **Tests**

### **Exécuter les tests**

Pour exécuter les tests unitaires, utilisez la commande suivante :

```bash
uv run pytest
```

Les tests sont organisés par module dans les répertoires test, test et test.

---

## **Déploiement**

### **Docker**

Un fichier Dockerfile est fourni pour déployer l'application dans un conteneur Docker.

1. **Construire l'image Docker** :

   ```bash
   docker build -t clea-api .
   ```

2. **Lancer le conteneur** :

   ```bash
   docker run -p 8080:8080 clea-api
   ```

---

## **Contribuer**

Les contributions sont les bienvenues ! Veuillez suivre les étapes suivantes pour contribuer :

1. Forkez le dépôt.
2. Créez une branche pour votre fonctionnalité ou correction de bug.
3. Soumettez une pull request avec une description claire de vos modifications.

---

## **Licence**

Ce projet est sous licence MIT. Consultez le fichier LICENSE pour plus d'informations.
