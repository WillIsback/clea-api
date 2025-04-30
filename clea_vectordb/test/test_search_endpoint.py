import requests

BASE_URL = "http://localhost:8080"
DATABASE_URL = f"{BASE_URL}/database"
SEARCH_URL = f"{BASE_URL}/search"

def list_documents():
    url = f"{DATABASE_URL}/list_documents"
    response = requests.get(url)
    assert response.status_code == 200, f"Erreur lors de la récupération des documents : {response.json()}"
    return response.json()

def delete_all_documents():
    documents = list_documents()
    for doc in documents:
        delete_document(doc["id"])
    print("Tous les documents ont été supprimés de la base de données.")
    
def add_documents():
    url = f"{DATABASE_URL}/add_document"
    payload = [
        {
            "title": "Guide de remboursement des frais professionnels (test unique)",
            "content": "Les frais professionnels doivent être soumis dans le mois suivant leur engagement.",
            "theme": "Finance",
            "document_type": "Guide",
            "publish_date": "2025-01-01"
        },
        {
            "title": "Procédure de mutation interne (test unique)",
            "content": "Les salariés souhaitant effectuer une mutation interne doivent avoir passé au moins 18 mois à leur poste actuel.",
            "theme": "RH",
            "document_type": "Procédure",
            "publish_date": "2025-02-15"
        },
        {
            "title": "Introduction à la programmation Python (test unique)",
            "content": "Ce document explique les bases de la programmation en Python, y compris les variables, les boucles et les fonctions.",
            "theme": "Informatique",
            "document_type": "Tutoriel",
            "publish_date": "2025-03-10"
        }
    ]

    # Ajouter les nouveaux documents
    response = requests.post(url, json=payload)
    assert response.status_code == 200, f"Erreur lors de l'ajout des documents : {response.json()}"
    added_documents = response.json()
    assert len(added_documents) == len(payload), "Le nombre de documents ajoutés ne correspond pas à la demande."
    print(f"Documents ajoutés : \n{added_documents}\n")
    return [doc["id"] for doc in added_documents]

def search_document(query, top_k=10, theme=None, document_type=None):
    url = f"{SEARCH_URL}/hybrid_search"
    payload = {
        "query": query,
        "top_k": top_k,
        "theme": theme,
        "document_type": document_type
    }
    response = requests.post(url, json=payload)
    assert response.status_code == 200, f"Erreur lors de la recherche : {response.json()}"
    search_results = response.json()
    print(f"Résultats bruts de la recherche : \n{search_results}\n")
    return search_results

def delete_document(document_id):
    url = f"{DATABASE_URL}/delete_document"
    params = {"document_id": document_id}
    response = requests.delete(url, params=params)
    assert response.status_code == 200, f"Erreur lors de la suppression du document : {response.json()}"
    assert response.json().get("success"), "Le document n'a pas été supprimé avec succès."

def cleanup_test_documents(document_ids):
    for document_id in document_ids:
        delete_document(document_id)

def test_search_endpoint():
    # Étape 0 : Nettoyer complètement la base de données
    delete_all_documents()

    # Étape 1 : Ajouter des documents
    document_ids = add_documents()

    # Étape 2 : Effectuer une recherche
    query = "programmation Python"
    search_results = search_document(query=query, top_k=1)
    print(f"Résultats bruts de la recherche : {search_results}")
    assert search_results["total_results"] > 0, "Aucun résultat trouvé pour la recherche."
    top_result = search_results["results"][0]
    print(f"\nRésultat de la recherche : \n{top_result}\n")
    assert top_result["title"] == "Introduction à la programmation Python (test unique)", "Le document retourné n'est pas celui attendu."

    # Étape 3 : Nettoyer la base de données
    cleanup_test_documents(document_ids)