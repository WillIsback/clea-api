"""Tests unitaires pour les endpoints de pipeline.

Ce module contient des tests pour vérifier le bon fonctionnement des
opérations de traitement de documents et leur insertion dans la base de données.
"""
import pytest
import os
import requests
import logging
from pathlib import Path
import tempfile
from typing import Dict, List, Any, Optional

# Configuration du logger pour les tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# URLs des endpoints
PIPELINE_URL = "http://localhost:8080/pipeline"
DATABASE_URL = "http://localhost:8080/database"


@pytest.fixture
def demo_files():
    """Fixture pour récupérer les fichiers de démonstration dans différents formats.
    
    Returns:
        Dict[str, Path]: Dictionnaire contenant le chemin vers chaque fichier de démonstration 
            (clés : 'txt', 'json', 'docx', 'pdf', 'html').
    """
    demo_dir = Path("demo")
    files = {}
    
    # Rechercher les fichiers de démonstration
    for ext in ["txt", "json", "docx", "pdf", "html"]:
        file_path = demo_dir / f"demo.{ext}"
        if file_path.exists():
            files[ext] = file_path
        else:
            logger.warning(f"Fichier de démonstration {file_path} non trouvé")
    
    # Si aucun fichier n'est trouvé, créer un fichier temporaire
    if not files:
        logger.warning("Aucun fichier de démonstration trouvé, création d'un fichier temporaire")
        temp_dir = tempfile.mkdtemp()
        temp_file = Path(temp_dir) / "temp_demo.txt"
        
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("Ceci est un contenu simulé pour le test.\n" * 20)
        
        files["txt"] = temp_file
        
        yield files
        
        # Nettoyage des fichiers temporaires
        if temp_file.exists():
            temp_file.unlink()
        if Path(temp_dir).exists():
            Path(temp_dir).rmdir()
    else:
        yield files


def list_documents():
    """Récupère la liste des documents dans la base de données.
    
    Returns:
        List[Dict[str, Any]]: Liste des documents avec leurs métadonnées.
        
    Raises:
        AssertionError: Si la requête échoue.
    """
    url = f"{DATABASE_URL}/documents"
    response = requests.get(url)
    assert response.status_code == 200, f"Erreur lors de la récupération des documents : {response.text}"
    return response.json()


def delete_document(document_id: int):
    """Supprime un document de la base de données.
    
    Args:
        document_id: ID du document à supprimer.
        
    Raises:
        AssertionError: Si la suppression échoue.
    """
    url = f"{DATABASE_URL}/documents/{document_id}"
    response = requests.delete(url)
    assert response.status_code == 200, f"Erreur lors de la suppression du document : {response.text}"
    assert "success" in response.json(), "Le document n'a pas été supprimé avec succès."


def delete_all_test_documents():
    """Supprime tous les documents de test de la base de données.
    
    Supprime uniquement les documents dont le thème est "Test" ou "Thème générique".
    """
    documents = list_documents()
    deleted_count = 0
    
    for doc in documents:
        if doc.get("theme") in ["Test", "Thème générique", "Test thème"]:
            delete_document(doc["id"])
            deleted_count += 1
    
    logger.info(f"{deleted_count} documents de test ont été supprimés de la base de données.")


def test_process_and_store_endpoint_txt(demo_files):
    """Teste le traitement et le stockage d'un fichier texte.
    
    Vérifie que l'endpoint /process-and-store traite correctement un fichier TXT
    et l'insère dans la base de données avec les métadonnées appropriées.
    
    Args:
        demo_files: Fixture contenant les chemins vers les fichiers de démonstration.
    """
    # Vérifier que le fichier de démonstration TXT existe
    if "txt" not in demo_files:
        pytest.skip("Fichier de démonstration TXT non disponible")
    
    # Nettoyer les documents de test existants
    delete_all_test_documents()
    
    # Paramètres du test
    txt_file = demo_files["txt"]
    theme = "Test thème"
    max_length = 500
    overlap = 100
    
    # Envoyer la requête au endpoint
    with open(txt_file, "rb") as file:
        response = requests.post(
            f"{PIPELINE_URL}/process-and-store",
            files={"file": (txt_file.name, file, "text/plain")},
            data={
                "max_length": str(max_length), 
                "overlap": str(overlap),
                "theme": theme
            }
        )
    
    # Vérifier la réponse
    assert response.status_code == 200, f"Erreur lors du traitement du fichier TXT: {response.text}"
    result = response.json()
    
    # Vérifier les informations du résultat
    assert "document_id" in result, "La réponse ne contient pas l'ID du document"
    assert "chunks" in result, "La réponse ne contient pas le nombre de chunks"
    assert "corpus_id" in result, "La réponse ne contient pas l'ID du corpus"
    assert "file_path" in result, "La réponse ne contient pas le chemin du fichier"
    assert "original_filename" in result, "La réponse ne contient pas le nom du fichier original"
    
    document_id = result["document_id"]
    logger.info(f"Document TXT ajouté avec ID: {document_id}, chunks: {result['chunks']}")
    
    # Vérifier que le document existe bien dans la base de données
    documents = list_documents()
    matching_docs = [doc for doc in documents if doc["id"] == document_id]
    
    assert len(matching_docs) == 1, f"Document {document_id} non trouvé dans la base de données"
    document = matching_docs[0]
    
    assert document["theme"] == theme, f"Le thème du document est incorrect: {document['theme']} au lieu de {theme}"
    assert document["document_type"] == "TXT", f"Le type du document est incorrect: {document['document_type']}"
    
    # Nettoyer
    delete_document(document_id)


def test_process_and_store_endpoint_json(demo_files):
    """Teste le traitement et le stockage d'un fichier JSON.
    
    Vérifie que l'endpoint /process-and-store traite correctement un fichier JSON
    et l'insère dans la base de données avec les métadonnées appropriées.
    
    Args:
        demo_files: Fixture contenant les chemins vers les fichiers de démonstration.
    """
    # Vérifier que le fichier de démonstration JSON existe
    if "json" not in demo_files:
        pytest.skip("Fichier de démonstration JSON non disponible")
    
    # Nettoyer les documents de test existants
    delete_all_test_documents()
    
    # Paramètres du test
    json_file = demo_files["json"]
    theme = "Test JSON"
    max_length = 500
    overlap = 100
    
    # Envoyer la requête au endpoint
    with open(json_file, "rb") as file:
        response = requests.post(
            f"{PIPELINE_URL}/process-and-store",
            files={"file": (json_file.name, file, "application/json")},
            data={
                "max_length": str(max_length), 
                "overlap": str(overlap),
                "theme": theme
            }
        )
    
    # Vérifier la réponse
    assert response.status_code == 200, f"Erreur lors du traitement du fichier JSON: {response.text}"
    result = response.json()
    
    # Vérifier les informations du résultat
    assert "document_id" in result, "La réponse ne contient pas l'ID du document"
    assert "chunks" in result, "La réponse ne contient pas le nombre de chunks"
    
    document_id = result["document_id"]
    logger.info(f"Document JSON ajouté avec ID: {document_id}, chunks: {result['chunks']}")
    
    # Nettoyer
    delete_document(document_id)


def test_process_and_store_endpoint_pdf(demo_files):
    """Teste le traitement et le stockage d'un fichier PDF.
    
    Vérifie que l'endpoint /process-and-store traite correctement un fichier PDF
    et l'insère dans la base de données avec les métadonnées appropriées.
    
    Args:
        demo_files: Fixture contenant les chemins vers les fichiers de démonstration.
    """
    # Vérifier que le fichier de démonstration PDF existe
    if "pdf" not in demo_files:
        pytest.skip("Fichier de démonstration PDF non disponible")
    
    # Nettoyer les documents de test existants
    delete_all_test_documents()
    
    # Paramètres du test
    pdf_file = demo_files["pdf"]
    theme = "Test PDF"
    max_length = 500
    overlap = 100
    
    # Envoyer la requête au endpoint
    with open(pdf_file, "rb") as file:
        response = requests.post(
            f"{PIPELINE_URL}/process-and-store",
            files={"file": (pdf_file.name, file, "application/pdf")},
            data={
                "max_length": str(max_length), 
                "overlap": str(overlap),
                "theme": theme
            }
        )
    
    # Vérifier la réponse
    assert response.status_code == 200, f"Erreur lors du traitement du fichier PDF: {response.text}"
    result = response.json()
    
    # Vérifier les informations du résultat
    assert "document_id" in result, "La réponse ne contient pas l'ID du document"
    
    document_id = result["document_id"]
    logger.info(f"Document PDF ajouté avec ID: {document_id}, chunks: {result['chunks']}")
    
    # Nettoyer
    delete_document(document_id)


def test_process_and_store_async_endpoint(demo_files):
    """Teste le traitement asynchrone d'un fichier.
    
    Vérifie que l'endpoint /process-and-store-async lance correctement
    une tâche de traitement en arrière-plan.
    
    Args:
        demo_files: Fixture contenant les chemins vers les fichiers de démonstration.
    """
    # Utiliser n'importe quel fichier disponible
    available_ext = next(iter(demo_files.keys()))
    file_path = demo_files[available_ext]
    
    # Paramètres du test
    theme = "Test Async"
    max_length = 500
    overlap = 100
    
    # Envoyer la requête au endpoint asynchrone
    with open(file_path, "rb") as file:
        response = requests.post(
            f"{PIPELINE_URL}/process-and-store-async",
            files={"file": (file_path.name, file, "application/octet-stream")},
            data={
                "max_length": str(max_length), 
                "overlap": str(overlap),
                "theme": theme
            }
        )
    
    # Vérifier la réponse
    assert response.status_code == 200, f"Erreur lors du lancement du traitement asynchrone: {response.text}"
    result = response.json()
    
    # Vérifier les informations de la tâche asynchrone
    assert "task_id" in result, "La réponse ne contient pas l'ID de la tâche"
    assert "status" in result, "La réponse ne contient pas le statut de la tâche"
    assert result["status"] == "processing", "Le statut de la tâche n'est pas 'processing'"
    
    logger.info(f"Tâche asynchrone lancée avec ID: {result['task_id']}")


def test_process_multiple_file_types(demo_files):
    """Teste le traitement de plusieurs types de fichiers.
    
    Vérifie que l'endpoint /process-and-store peut traiter différents formats
    de fichiers et les insérer correctement dans la base de données.
    
    Args:
        demo_files: Fixture contenant les chemins vers les fichiers de démonstration.
    """
    # Nettoyer les documents de test existants
    delete_all_test_documents()
    
    results = {}
    
    # Traiter chaque type de fichier disponible
    for ext, file_path in demo_files.items():
        # Paramètres du test
        theme = f"Test {ext.upper()}"
        max_length = 500
        overlap = 100
        
        # Envoyer la requête au endpoint
        with open(file_path, "rb") as file:
            response = requests.post(
                f"{PIPELINE_URL}/process-and-store",
                files={"file": (file_path.name, file, "application/octet-stream")},
                data={
                    "max_length": str(max_length), 
                    "overlap": str(overlap),
                    "theme": theme
                }
            )
        
        # Vérifier la réponse
        if response.status_code == 200:
            result = response.json()
            if "document_id" in result:
                results[ext] = result["document_id"]
                logger.info(f"Document {ext.upper()} ajouté avec ID: {result['document_id']}")
            else:
                logger.warning(f"Traitement du fichier {ext} réussi mais sans document_id")
        else:
            logger.warning(f"Échec du traitement du fichier {ext}: {response.text}")
    
    # Vérifier qu'au moins un fichier a été traité avec succès
    assert results, "Aucun fichier n'a été traité avec succès"
    
    # Vérifier que les documents existent dans la base de données
    documents = list_documents()
    doc_ids = {doc["id"] for doc in documents}
    
    for ext, doc_id in results.items():
        assert doc_id in doc_ids, f"Document {ext} avec ID {doc_id} non trouvé dans la base de données"
    
    # Nettoyer
    for doc_id in results.values():
        delete_document(doc_id)


def test_corpus_creation(demo_files):
    """Teste la création d'un corpus avec plusieurs documents.
    
    Vérifie que l'endpoint /process-and-store peut ajouter plusieurs documents
    au même corpus et que les index sont correctement gérés.
    
    Args:
        demo_files: Fixture contenant les chemins vers les fichiers de démonstration.
    """
    if len(demo_files) < 2:
        pytest.skip("Pas assez de fichiers de démonstration pour tester la création de corpus")
    
    # Nettoyer les documents de test existants
    delete_all_test_documents()
    
    # Créer un corpus_id unique
    corpus_id = f"test-corpus-{os.urandom(4).hex()}"
    theme = "Test Corpus"
    max_length = 500
    overlap = 100
    
    document_ids = []
    
    # Ajouter plusieurs documents au même corpus
    for i, (ext, file_path) in enumerate(list(demo_files.items())[:2]):
        with open(file_path, "rb") as file:
            response = requests.post(
                f"{PIPELINE_URL}/process-and-store",
                files={"file": (file_path.name, file, "application/octet-stream")},
                data={
                    "max_length": str(max_length), 
                    "overlap": str(overlap),
                    "theme": theme,
                    "corpus_id": corpus_id
                }
            )
        
        assert response.status_code == 200, f"Erreur lors de l'ajout du document {i+1}: {response.text}"
        result = response.json()
        
        # Vérifier que le document a été ajouté au bon corpus
        assert result["corpus_id"] == corpus_id, f"Corpus_id incorrect: {result['corpus_id']} au lieu de {corpus_id}"
        
        document_ids.append(result["document_id"])
        
        # Pour le premier document, vérifier si un index doit être créé
        if i == 0 and result.get("create_index"):
            # Créer l'index pour le corpus
            index_url = f"{DATABASE_URL}/indexes/{corpus_id}/create"
            index_response = requests.post(index_url)
            
            assert index_response.status_code == 200, f"Erreur lors de la création de l'index: {index_response.text}"
            logger.info(f"Index créé pour le corpus {corpus_id}")
    
    # Vérifier que les documents ont été ajoutés au corpus
    documents = list_documents()
    corpus_docs = [doc for doc in documents if doc.get("corpus_id") == corpus_id]
    
    assert len(corpus_docs) == len(document_ids), f"Nombre incorrect de documents dans le corpus: {len(corpus_docs)}"
    
    # Nettoyer
    for doc_id in document_ids:
        delete_document(doc_id)


if __name__ == "__main__":
    """Exécution manuelle des tests."""
    try:
        # Récupérer les fichiers de démonstration
        from pathlib import Path
        demo_dir = Path("demo")
        files = {}
        
        for ext in ["txt", "json", "docx", "pdf", "html"]:
            file_path = demo_dir / f"demo.{ext}"
            if file_path.exists():
                files[ext] = file_path
        
        if not files:
            print("Aucun fichier de démonstration trouvé. Exécutez d'abord le script demo/script.py.")
            exit(1)
        
        print(f"Fichiers de démonstration trouvés: {', '.join(files.keys())}")
        
        # Exécuter les tests
        print("\n1. Test de traitement d'un fichier TXT")
        test_process_and_store_endpoint_txt(files)
        
        print("\n2. Test de traitement d'un fichier JSON")
        test_process_and_store_endpoint_json(files)
        
        print("\n3. Test de traitement d'un fichier PDF")
        test_process_and_store_endpoint_pdf(files)
        
        print("\n4. Test de traitement asynchrone")
        test_process_and_store_async_endpoint(files)
        
        print("\n5. Test de traitement de plusieurs types de fichiers")
        test_process_multiple_file_types(files)
        
        print("\n6. Test de création d'un corpus")
        test_corpus_creation(files)
        
        print("\nTous les tests ont réussi!")
        
    except Exception as e:
        print(f"ERREUR: {str(e)}")
        raise
        
    finally:
        print("\nNettoyage des documents de test...")
        delete_all_test_documents()
        print("Tests terminés.")