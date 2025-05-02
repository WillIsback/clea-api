import os
import json
import pytest
from datetime import date
from doc_loader.src import DocsLoader, UnsupportedFileTypeError
from doc_loader.src.base import DocumentWithChunks


@pytest.fixture
def temp_dir(tmp_path):
    """
    Crée un répertoire temporaire pour les tests.

    Args:
        tmp_path: Répertoire temporaire fourni par pytest.

    Returns:
        Path: Chemin vers le répertoire temporaire.
    """
    return tmp_path


def create_temp_file(temp_dir, filename, content):
    """
    Crée un fichier temporaire avec le contenu spécifié.

    Args:
        temp_dir: Répertoire temporaire.
        filename: Nom du fichier à créer.
        content: Contenu à écrire dans le fichier.

    Returns:
        Path: Chemin vers le fichier temporaire créé.
    """
    file_path = temp_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


def test_extract_from_txt(temp_dir):
    """
    Teste l'extraction d'un fichier TXT.

    Args:
        temp_dir: Répertoire temporaire pour le test.
    """
    file_path = create_temp_file(temp_dir, "test.txt", "Ceci est un test.")
    loader = DocsLoader(str(file_path))
    doc = loader.extract_documents(max_length=50)
    assert isinstance(doc, DocumentWithChunks)
    assert "Ceci est un test." in doc.chunks[0].content
    assert doc.document.document_type == "TXT"


def test_extract_from_html(temp_dir):
    """
    Teste l'extraction d'un fichier HTML.

    Args:
        temp_dir: Répertoire temporaire pour le test.
    """
    html = "<html><head><title>Titre</title></head><body>Corps du texte</body></html>"
    file_path = create_temp_file(temp_dir, "test.html", html)
    loader = DocsLoader(str(file_path))
    doc = loader.extract_documents(max_length=50)
    assert isinstance(doc, DocumentWithChunks)
    assert "Corps du texte" in doc.chunks[0].content
    assert doc.document.document_type == "HTML"


def test_extract_from_json(temp_dir):
    """
    Teste l'extraction d'un fichier JSON.

    Args:
        temp_dir: Répertoire temporaire pour le test.
    """
    content = [
        {
            "title": "Doc JSON",
            "content": "Texte JSON",
            "theme": "Test",
            "document_type": "JSON",
            "publish_date": str(date.today()),
        }
    ]
    file_path = create_temp_file(temp_dir, "test.json", json.dumps(content))
    loader = DocsLoader(str(file_path))
    doc = loader.extract_documents(max_length=50)
    assert isinstance(doc, DocumentWithChunks)
    assert doc.document.title == "Doc JSON"
    assert doc.document.document_type == "JSON"
    assert "Texte JSON" in doc.chunks[0].content


def test_unsupported_extension(temp_dir):
    """
    Teste le comportement pour une extension de fichier non supportée.

    Args:
        temp_dir: Répertoire temporaire pour le test.
    """
    file_path = create_temp_file(temp_dir, "file.xyz", "Contenu non supporté")
    with pytest.raises(UnsupportedFileTypeError):
        DocsLoader(str(file_path)).extract_documents()


def test_cleanup_file(temp_dir):
    """
    Teste la suppression d'un fichier temporaire.

    Args:
        temp_dir: Répertoire temporaire pour le test.
    """
    file_path = create_temp_file(temp_dir, "cleanup.txt", "Texte")
    assert file_path.exists()
    os.remove(file_path)
    assert not file_path.exists()
