import pytest
from pathlib import Path
import tempfile
import requests


PIPELINE_URL = "http://localhost:8080/pipeline"
DATABASE_URL = "http://localhost:8080/database"


@pytest.fixture
def demo_file():
    """Fixture pour utiliser demo/short_demo.json ou créer un fichier temporaire."""
    file_path = Path("demo/short_demo.json")
    if file_path.exists():
        yield file_path
    else:
        # Crée un fichier temporaire si demo/short_demo.json n'existe pas
        temp_dir = tempfile.mkdtemp()
        temp_file = Path(temp_dir) / "short_demo.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("Ceci est un contenu simulé pour le test.\n" * 10)
        yield temp_file
        temp_file.unlink()  # Supprime le fichier après le test
        Path(temp_dir).rmdir()  # Supprime le répertoire temporaire


def list_documents():
    url = f"{DATABASE_URL}/list_documents"
    response = requests.get(url)
    assert response.status_code == 200, (
        f"Erreur lors de la récupération des documents : {response.json()}"
    )
    return response.json()  # Retourne la liste des documents


def delete_document(document_id):
    url = f"{DATABASE_URL}/delete_document"
    params = {"document_id": document_id}
    response = requests.delete(url, params=params)
    assert response.status_code == 200, (
        f"Erreur lors de la suppression du document : {response.json()}"
    )
    assert response.json().get("success"), (
        "Le document n'a pas été supprimé avec succès."
    )


def delete_all_documents():
    documents = list_documents()
    for doc in documents:
        delete_document(doc["id"])
    print("Tous les documents ont été supprimés de la base de données.")


def test_process_and_store_endpoint(demo_file):
    """Test du endpoint /process-and-store."""

    # Étape 0 : Nettoyer complètement la base de données
    delete_all_documents()

    # Envoie une requête POST au endpoint
    with open(demo_file, "rb") as file:
        response = requests.post(
            f"{PIPELINE_URL}/process-and-store",
            files={"file": (demo_file.name, file, "text/plain")},
            params={"max_length": "1000", "theme": "Test thème"},
        )

    # Vérifie que la réponse est correcte
    assert response.status_code == 200, f"Erreur : {response.json()}"
    data = response.json()

    # Vérifie que les résultats sont conformes
    assert len(data) > 0, "Aucun document n'a été ajouté."
    assert all("id" in doc for doc in data), "Certains documents n'ont pas d'ID."
    assert all("title" in doc for doc in data), "Certains documents n'ont pas de titre."
    assert all("content" in doc for doc in data), (
        "Certains documents n'ont pas de contenu."
    )
    assert all(doc["theme"] == "Test thème" for doc in data), (
        "Le thème des documents est incorrect."
    )

    delete_all_documents()
