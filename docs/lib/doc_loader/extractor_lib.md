# Librairie **doc_loader** (Extraction de documents)

Ce module fournit une abstraction et des implémentations concrètes pour charger et découper des documents de différents formats en **`DocumentWithChunks`**, prêt à être injecté dans la base de données via l’API **vectordb**.

---

## Installation

La librairie `doc_loader` fait partie du package **`clea-doc-loader`**. Elle se charge automatiquement des dépendances via votre `pyproject.toml` / `requirements.txt`.

```bash
# depuis la racine du projet
uv install .
````

---

## Structure du package

```
doc_loader/
├── extractor_factory.py    # Sélection de l’extracteur selon l’extension
├── base.py                 # Interface et helpers communs
├── docs_loader.py          # Point d’entrée : DocsLoader
└── data_extractor/         # 5 extracteurs concrets
    ├── txt_extractor.py    # .txt
    ├── json_extractor.py   # .json
    ├── docx_extractor.py   # .docx
    ├── html_extractor.py   # .html
    └── pdf_extractor.py    # .pdf
```

---

## 1. Interface commune

### `BaseExtractor` (`base.py`)&#x20;

```python
class BaseExtractor(ABC):
    def __init__(self, file_path: str) -> None:
        """Chemin vers le fichier à traiter."""
        self.file_path = Path(file_path)

    @abstractmethod
    def extract_one(self, *, max_length: int = 1000) -> DocumentWithChunks:
        """
        Extrait l’ensemble du document en un seul objet `DocumentWithChunks`.
        
        Args:
            max_length: taille cible des chunks finaux.
        Returns:
            DocumentWithChunks(document: DocumentCreate, chunks: List[ChunkCreate])
        """
```

---

## 2. Constructeur de payloads

### `build_document_with_chunks(...)` (`base.py`)&#x20;

Cette fonction choisit automatiquement entre :

1. **Mini-document** (un seul chunk si `len(full_text) ≤ max_length`),
2. **Segmentation sémantique** (via NLP, `_semantic_segmentation`),
3. **Fallback** (découpage fixe + overlap).

```python
doc_with_chunks = build_document_with_chunks(
    title="Rapport 2024",
    theme="RSE",
    document_type="PDF",
    publish_date=date.today(),
    max_length=1000,
    full_text= "... texte complet ..."
)
# → DocumentWithChunks(document=DocumentCreate(...),
#                      chunks=[ChunkCreate(...), ...])
```

---

## 3. Sélection de l’extracteur

### `get_extractor(file_path: str) → BaseExtractor` (`extractor_factory.py`)&#x20;

```python
ext = get_extractor("/chemin/vers/fichier.docx")
# ext est une instance de DocxExtractor, PdfExtractor, JsonExtractor, HtmlExtractor ou TxtExtractor.
```

* Lève `UnsupportedFileTypeError` pour les extensions non listées.

---

## 4. Point d’entrée : `DocsLoader`

### `DocsLoader` (`docs_loader.py`)&#x20;

```python
loader = DocsLoader("/chemin/fichier.txt")
doc_with_chunks = loader.extract_documents(max_length=1200)
# renvoie un DocumentWithChunks unique
```

* `extract_documents(...)` délègue à `extract_one()` de l’extracteur choisi.

---

## 5. Exemple détaillé : **TxtExtractor**

### `TxtExtractor` (`txt_extractor.py`)&#x20;

```python
class TxtExtractor(BaseExtractor):
    def extract_one(self, max_length: int = 1000) -> DocumentWithChunks:
        # 1) lit tout le fichier
        # 2) détecte si c’est un JSON listé → extrait métadonnées + contenu
        # 3) sinon, métadonnées par défaut (stem, "Générique", date.today())
        # 4) appelle build_document_with_chunks(...)
```

* Gère automatiquement :

  * Fichiers TXT « bruts »
  * Fichiers TXT au format JSON `[{"title":…, "theme":…, "publish_date":…, "content":…}, …]`

---

## 6. Autres extracteurs

Chaque extracteur hérite de `BaseExtractor` et implémente `extract_one(...)` de manière similaire, en utilisant :

* **DocxExtractor** (`.docx`) → segmentation par paragraphes et métadonnées Office ﹒
* **PdfExtractor** (`.pdf`) → lecture `pypdf`, segmentation **stream** ou **adaptive** ﹒
* **HtmlExtractor** (`.html`) → `BeautifulSoup`, `get_text()`, segmentation ﹒
* **JsonExtractor** (`.json`) → parse JSON, extrait `entries` et segmente le contenu.

Vous retrouverez la logique spécifique dans `data_extractor/{docx,json,html,pdf}_extractor.py`.

---

## 7. Usage typique

```python
from doc_loader.docs_loader import DocsLoader

# 1. Choix de l’extracteur et extraction
loader = DocsLoader("mon_fichier.pdf")
doc_payload = loader.extract_documents(max_length=800)

# 2. Insertion en base (via vectordb)
from vectordb.src.database import get_db, add_document_with_chunks
db = next(get_db())
result = add_document_with_chunks(db, doc_payload.document, doc_payload.chunks)
```

---

> Module `doc_loader` stable – dernière mise à jour : **02 mai 2025**.
