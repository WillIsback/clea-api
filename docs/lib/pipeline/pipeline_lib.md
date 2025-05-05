# Module **pipeline**

Orchestration du traitement de documents : extraction, segmentation et insertion en base.

---

## Installation

Le module `pipeline.py` fait partie du package **clea-pipeline**. Pour l’installer :

```bash
pip install clea-pipeline
````

---

## Fonctions principales

### `process_and_store`&#x20;

```python
def process_and_store(
    file_path: str,
    max_length: int = 500,
    overlap: int = 100,
    theme: Optional[str] = "Thème générique",
    corpus_id: Optional[str] = None,
) -> Dict[str, Any]:
```

#### Description

1. **Vérifie** que le fichier existe (lève `FileNotFoundError` sinon).
2. **Extrait** et segmente le document en chunks hiérarchiques via `DocsLoader`.
3. **Applique** le thème si fourni.
4. **Insère** le document et ses chunks en base via `add_document_with_chunks`.
5. **Retourne** le résultat contenant :

   * `document_id` : ID du document créé
   * `chunks` : nombre de chunks insérés
   * `corpus_id` : UUID du corpus
   * `create_index` : booléen indiquant si un index doit être (re)créé
   * `index_message` : message d’instruction pour la création d’index (si applicable)

#### Paramètres

| Nom          | Type            | Description                                  |
| ------------ | --------------- | -------------------------------------------- |
| `file_path`  | `str`           | Chemin vers le fichier à traiter             |
| `max_length` | `int`           | Taille max d’un chunk final (défaut 500)     |
| `overlap`    | `int`           | Chevauchement entre chunks (défaut 100)      |
| `theme`      | `Optional[str]` | Thème à appliquer (défaut "Thème générique") |
| `corpus_id`  | `Optional[str]` | UUID du corpus (généré si None)              |

#### Retour

```json
{
  "document_id": 1,
  "chunks": 2,
  "corpus_id": "e0428ce9-4a0a-445d-8f35-f5c9bed89c67",
  "create_index": true,
  "index_message": "Un nouvel index pour le corpus … doit être créé. Utilisez POST /database/indexes/{corpus_id}/create."
}
```

#### Exceptions

* `FileNotFoundError` : si `file_path` inexistant
* `ValueError` : si aucune extraction ou si l’insertion échoue

#### Exemple

```python
from pipeline import process_and_store

result = process_and_store(
    "demo/report.pdf",
    max_length=800,
    overlap=150,
    theme="Finance",
)
print(result)
# {
#   "document_id": 10,
#   "chunks": 42,
#   "corpus_id": "abcd-1234-…",
#   "create_index": true,
#   "index_message": "…"
# }
```

---

### `determine_document_type`&#x20;

```python
def determine_document_type(file_path: str) -> str:
```

#### Description

Déduit le type du document (`PDF`, `TXT`, `WORD`, etc.) à partir de l’extension du fichier.

#### Paramètre

| Nom         | Type  | Description                    |
| ----------- | ----- | ------------------------------ |
| `file_path` | `str` | Chemin complet vers le fichier |

#### Retour

Une des valeurs suivantes :

```
PDF, TXT, MARKDOWN, WORD, HTML, XML, CSV, JSON, POWERPOINT, EXCEL, UNKNOWN
```

#### Exemple

```python
>>> determine_document_type("guide.docx")
"WORD"
>>> determine_document_type("notes.md")
"MARKDOWN"
```

---

## Utilisation typique

```python
from pipeline import process_and_store, determine_document_type

# 1. Déterminer le type (facultatif)
doc_type = determine_document_type("report.pdf")

# 2. Traiter et stocker en base
res = process_and_store(
    "report.pdf",
    max_length=1000,
    overlap=200,
    theme="RSE",
)
print(res)
```

---

> Module : `pipeline.py`
> Dernière mise à jour : 02 mai 2025
> Source : pipeline/src/pipeline.py&#x20;
