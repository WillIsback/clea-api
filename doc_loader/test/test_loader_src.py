import os
import json
import pytest
from datetime import date
from doc_loader.src import DocsLoader, ExtractedDocument, UnsupportedFileTypeError


# Crée un répertoire temporaire pour les tests
@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


def create_temp_file(temp_dir, filename, content):
    file_path = temp_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


def test_extract_from_txt(temp_dir):
    file_path = create_temp_file(temp_dir, "test.txt", "Ceci est un test.")
    loader = DocsLoader(str(file_path))
    docs = list(loader.extract_documents(max_length=50))
    assert len(docs) == 1
    assert isinstance(docs[0], ExtractedDocument)
    assert "Ceci est un test." in docs[0].content
    assert docs[0].document_type == "TXT"


def test_extract_from_html(temp_dir):
    html = "<html><head><title>Titre</title></head><body>Corps du texte</body></html>"
    file_path = create_temp_file(temp_dir, "test.html", html)
    loader = DocsLoader(str(file_path))
    docs = list(loader.extract_documents(max_length=50))
    assert len(docs) >= 1
    assert isinstance(docs[0], ExtractedDocument)
    assert "Corps du texte" in docs[0].content
    assert docs[0].document_type == "HTML"


def test_extract_from_json(temp_dir):
    content = [
        {
            "title": "Doc JSON",
            "content": "Texte JSON 1",
            "theme": "Test",
            "document_type": "JSON",
            "publish_date": str(date.today()),
        }
    ]
    file_path = create_temp_file(temp_dir, "test.json", json.dumps(content))
    loader = DocsLoader(str(file_path))
    docs = list(loader.extract_documents(max_length=50))
    assert len(docs) == 1
    assert docs[0].title == "Doc JSON"
    assert docs[0].document_type == "JSON"
    assert "Texte JSON" in docs[0].content


def test_unsupported_extension(temp_dir):
    file_path = create_temp_file(temp_dir, "file.xyz", "Contenu non supporté")
    with pytest.raises(UnsupportedFileTypeError):
        DocsLoader(str(file_path)).extract_documents()


def test_cleanup_file(temp_dir):
    file_path = create_temp_file(temp_dir, "cleanup.txt", "Texte")
    assert file_path.exists()
    os.remove(file_path)
    assert not file_path.exists()
