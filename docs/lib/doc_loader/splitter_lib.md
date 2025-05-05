# Librairie **splitter**

Ce module fournit des algorithmes de segmentation hiérarchique et sémantique de textes, avec des stratégies de secours pour les corpus non structurés. Il est conçu pour découper efficacement de grands documents en **chunks** exploitables par le pipeline d'indexation vectorielle.

---

## Table des matières

1. Constantes globales  
2. Segmentation principale  
   - `semantic_segmentation_stream`  
   - `_semantic_segmentation`  
   - `fallback_segmentation_stream`  
   - `_fallback_segmentation`  
3. Extraction sémantique  
   - `_extract_semantic_sections`  
   - `_extract_semantic_paragraphs`  
   - `_create_semantic_chunks`  
4. Utilitaires texte  
   - `_get_meaningful_preview`  
   - `is_sentence_boundary`  
   - `find_paragraph_boundaries`  
5. Exemple d'utilisation  

---

## 1. Constantes globales  

Définissent les paramètres limites pour le découpage et le mode de fonctionnement "stream" ou "fallback".

| Constante           | Valeur       | Description                                                        |
|---------------------|--------------|--------------------------------------------------------------------|
| `THRESHOLD_LARGE`   | 5 000 000    | Seuil (en octets) pour basculer en mode "stream" sur gros fichiers |
| `MAX_CHUNKS`        | 5 000        | Nombre max de chunks générés                                       |
| `MAX_TEXT_LENGTH`   | 20 000 000   | Longueur texte max supportée                                       |
| `MAX_CHUNK_SIZE`    | 8 000        | Taille max d'un chunk (chars)                                      |
| `MIN_LEVEL3_LENGTH` | 200          | Seuil min pour chunks niveau 3                                     |
| `MAX_LEVEL3_CHUNKS` | 100          | Nombre max de sous-chunks niveau 3 par paragraphe                  |

---

## 2. Segmentation principale (`segmentation.py`)

### `semantic_segmentation_stream(text: str, max_length: int) → Iterator[ChunkCreate]`

**Description:**
Réalise un découpage sémantique hiérarchique en 4 niveaux (0-3) avec gestion optimisée de la mémoire.

**Args:**

- text: Texte source à segmenter
- max_length: Longueur maximale souhaitée des chunks

**Yields:**

- Objets ChunkCreate générés séquentiellement (mode streaming)

**Étapes:**

1. Chunk racine (niveau 0)  
2. Sections sémantiques (niv. 1) via `_extract_semantic_sections`  
3. Paragraphes (niv. 2) via `_extract_semantic_paragraphs`  
4. Sous-chunks (niv. 3) via `_create_semantic_chunks`  

**Sécurité:**

- Évite les duplications
- S'arrête à `MAX_CHUNKS`

### `_semantic_segmentation(text: str, max_length: int) → List[ChunkCreate]`

**Description:**
Retourne la liste complète des chunks en utilisant le générateur `semantic_segmentation_stream`.

**Args:**

- text: Texte source à segmenter
- max_length: Longueur maximale souhaitée des chunks

**Returns:**

- Liste des chunks générés, limitée à `MAX_CHUNKS`

### `fallback_segmentation_stream(text: str, max_length: int) → Iterator[ChunkCreate]`

**Description:**
Méthode de segmentation de secours robuste pour textes non structurés.

**Args:**

- text: Texte source à segmenter
- max_length: Longueur maximale souhaitée des chunks

**Yields:**

- Objets ChunkCreate générés séquentiellement

**Stratégie:**

1. Chunk racine (aperçu)  
2. Segments glissants de taille `min(max_length*2, MAX_CHUNK_SIZE)`  
3. Tentatives de coupure naturelle (phrases, paragraphes)  
4. Chevauchement d'environ 10%

### `_fallback_segmentation(text: str, max_length: int) → List[ChunkCreate]`

**Description:**
Retourne la segmentation complète des chunks produits par `fallback_segmentation_stream`.

**Args:**

- text: Texte source à segmenter
- max_length: Longueur maximale souhaitée des chunks

**Returns:**

- Liste des chunks générés, limitée à `MAX_CHUNKS`

---

## 3. Extraction sémantique (`text_analysis.py`)

### `_extract_semantic_sections(text: str, max_sections: int = 20) → List[Dict]`

**Description:**
Identifie les sections sémantiques dans un texte.

**Args:**

- text: Texte à analyser
- max_sections: Nombre maximal de sections à extraire

**Returns:**

- Liste de dictionnaires `[{title, content, start_char, end_char}, ...]`

**Méthode:**

- Détecte titres formels (Markdown, soulignés) puis séparateurs naturels (sauts de ligne multiples)
- Si insuffisant, découpe artificiellement en blocs

### `_extract_semantic_paragraphs(text: str, base_offset: int = 0, max_paragraphs: int = 20) → List[Dict]`

**Description:**
Divise un texte en paragraphes sémantiques.

**Args:**

- text: Texte à analyser
- base_offset: Décalage de caractères à appliquer dans le document original
- max_paragraphs: Nombre maximal de paragraphes à extraire

**Returns:**

- Liste de dictionnaires `[{content, start_char, end_char}, ...]`

**Méthode:**

- Sépare sur `\n\n`
- Si trop peu de blocs, découpes par phrases ou artificiellement
- Regroupe petits blocs pour cohérence

### `_create_semantic_chunks(text: str, max_length: int, min_overlap: int = 50, base_offset: int = 0, max_chunks: int = 20) → List[Dict]`

**Description:**
Crée des chunks sémantiques à partir d'un texte.

**Args:**

- text: Texte à découper
- max_length: Longueur maximale d'un chunk
- min_overlap: Chevauchement minimal entre chunks consécutifs
- base_offset: Décalage de caractères à appliquer dans le document original
- max_chunks: Nombre maximal de chunks à générer

**Returns:**

- Liste de dictionnaires `[{content, start_char, end_char}, ...]`

**Méthode:**

- Découpage sur frontières de phrases ou paragraphes
- Ajustement de `effective_max` et `effective_overlap` selon longueur du texte

---

## 4. Utilitaires texte (`text_utils.py`)

### `_get_meaningful_preview(text: str, max_length: int) → str`

**Description:**
Extrait un aperçu significatif d'un texte.

**Args:**

- text: Texte source
- max_length: Longueur maximale de l'aperçu

**Returns:**

- Aperçu combinant début, phrases clés et fin du texte

**Méthode:**

1. Extrait du début du texte  
2. Sélectionne phrases clés du milieu (contenant: "essentiel", "clé", etc.)  
3. Inclut la fin du texte

### `is_sentence_boundary(text: str, pos: int) → bool`

**Description:**
Vérifie si une position donnée correspond à une frontière de phrase.

**Args:**

- text: Texte à analyser
- pos: Position à vérifier

**Returns:**

- True si la position marque une fin de phrase, False sinon

**Critères:**
Présence de `. ! ?` suivi d'un espace ou de la fin de chaîne.

### `find_paragraph_boundaries(text: str) → List[int]`

**Description:**
Identifie les positions de début de chaque paragraphe.

**Args:**

- text: Texte à analyser

**Returns:**

- Liste des indices de début de paragraphe

**Méthode:**
Détection des séparations de type `\n\s*\n`.

---

## 5. Exemple d'utilisation

```python
from splitter.segmentation import semantic_segmentation_stream, fallback_segmentation_stream

text = open("mon_document.txt", "r", encoding="utf-8").read()

# 1. Segmentation sémantique (recommandée)
chunks = list(semantic_segmentation_stream(text, max_length=1000))
print(f"{len(chunks)} chunks générés (niveaux 0–3)")

# 2. Fallback si échec ou corpus simple
if len(chunks) == 1:
    chunks = list(fallback_segmentation_stream(text, max_length=800))
    print(f"Fallback : {len(chunks)} chunks générés")

```
