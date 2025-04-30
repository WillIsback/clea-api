import pytest
import requests
from pathlib import Path
import tempfile

# Création d'un client de test pour FastAPI
BASE_URL = "http://localhost:8080/doc_loader"


@pytest.fixture
def temp_file():
    """Fixture pour créer un fichier temporaire pour les tests."""
    temp_dir = tempfile.mkdtemp()
    file_path = Path(temp_dir) / "test.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Ceci est un test.\n" * 10)
    yield file_path
    file_path.unlink()  # Supprime le fichier après le test
    Path(temp_dir).rmdir()  # Supprime le répertoire temporaire


def test_process_file(temp_file):
    """Test du endpoint /upload-file."""
    with open(temp_file, "rb") as file:
        response = requests.post(
            f"{BASE_URL}/upload-file",
            files={"file": (temp_file.name, file, "text/plain")},
            params={"max_length": "1000", "theme": "Test thème"},
        )

    assert response.status_code == 200, f"Erreur : {response.text}"
    data = response.json()
    # Ajoutez un print pour inspecter la réponse
    print("Réponse du serveur :", data)
    # Vérifie que les résultats sont conformes
    assert all("content" in doc for doc in data)
    assert all(doc["theme"] == "Test thème" for doc in data)
