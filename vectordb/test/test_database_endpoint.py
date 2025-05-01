import requests

BASE_URL = "http://localhost:8080/database"

def add_document():
    url = f"{BASE_URL}/add_document"
    payload = [
        {
            "title": "Document de test",
            "content": "Ceci est un document de test pour vérifier les fonctionnalités CRUD.",
            "theme": "Test",
            "document_type": "Exemple",
            "publish_date": "2025-01-01"
        }
    ]
    response = requests.post(url, json=payload)
    assert response.status_code == 200, f"Erreur lors de l'ajout du document : {response.json()}"
    
    # La réponse est une liste de documents
    added_documents = response.json()
    print(f"length of added_documents: {len(added_documents)}")
    assert len(added_documents) == len(payload), "Le nombre de documents ajoutés ne correspond pas à la demande."
    return added_documents[0]["id"]  # Retourne l'ID du premier document ajouté

def list_documents():
    url = f"{BASE_URL}/list_documents"
    response = requests.get(url)
    assert response.status_code == 200, f"Erreur lors de la récupération des documents : {response.json()}"
    return response.json()  # Retourne la liste des documents

def update_document(document_id):
    url = f"{BASE_URL}/update_document"
    payload = {
        "document_id": document_id,
        "title": "Document de test (mis à jour)",
        "content": "Contenu mis à jour pour vérifier la fonctionnalité de mise à jour.",
        "theme": "Test - Mise à jour",
        "document_type": "Exemple - Mise à jour",
        "publish_date": "2025-02-01"
    }
    response = requests.put(url, json=payload)
    assert response.status_code == 200, f"Erreur lors de la mise à jour du document : {response.json()}"
    
    # Vérifie que le document mis à jour est retourné
    updated_document = response.json()
    assert updated_document["id"] == document_id, "L'ID du document mis à jour ne correspond pas."
    assert updated_document["title"] == payload["title"], "Le titre du document n'a pas été mis à jour correctement."

def delete_document(document_id):
    url = f"{BASE_URL}/delete_document"
    params = {"document_id": document_id}
    response = requests.delete(url, params=params)
    assert response.status_code == 200, f"Erreur lors de la suppression du document : {response.json()}"
    
    # Vérifie que la suppression a réussi
    result = response.json()
    assert "success" in result, f"Le document n'a pas été supprimé avec succès : {result}"

def cleanup_test_documents():
    documents = list_documents()
    for doc in documents:
        if "test" in doc["title"].lower():
            delete_document(doc["id"])
            
def delete_all_documents():
    documents = list_documents()
    for doc in documents:
        delete_document(doc["id"])
    print("Tous les documents ont été supprimés de la base de données.")
    
def test_crud_operations():
    # Étape 0 : Nettoyer complètement la base de données
    delete_all_documents()
    
    # Étape 1 : Ajouter un document
    document_id = add_document()

    # Étape 2 : Vérifier que le document est présent dans la liste
    documents = list_documents()
    assert any(doc["id"] == document_id for doc in documents), "Le document ajouté n'est pas présent dans la liste."

    # Étape 3 : Mettre à jour le document
    update_document(document_id)

    # Étape 4 : Supprimer le document
    delete_document(document_id)

    # Étape 5 : Vérifier que le document a été supprimé
    documents = list_documents()
    assert not any(doc["id"] == document_id for doc in documents), "Le document n'a pas été supprimé."

    # Nettoyage des documents de test
    cleanup_test_documents()