"""
doc_loader.base
===============

Outils communs d’extraction / segmentation pour tous les extracteurs
(PDF, DOCX, HTML, …).

* `ExtractedDocument` – schéma de sortie unique
* `BaseExtractor`     – interface abstraite
* `stream_split_to_disk` – découpe + overlap disque
* `adaptive_segmentation` – découpe hiérarchique Section → Paragraphe → Chunk
"""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Constantes                                                                   #
# --------------------------------------------------------------------------- #

_TEMP_DIR: Path = Path(tempfile.gettempdir())
_TEMP_DIR.mkdir(parents=True, exist_ok=True)
THRESHOLD_LARGE = 5_000_000 

# --------------------------------------------------------------------------- #
# Modèles Pydantic                                                             #
# --------------------------------------------------------------------------- #

class ExtractedDocument(BaseModel):
    """Document extrait ou chunké.

    Attributes
    ----------
    title :
        Titre (ou *titre (part n)*).
    content :
        Texte brut.
    theme :
        Thème métier.
    document_type :
        Type de fichier (PDF, DOCX, TXT…).
    publish_date :
        Date de publication.
    embedding :
        Embedding sérialisé (optionnel, sera ajouté plus tard).
    """

    title: str = Field(..., examples=["Rapport 2024 (part 3)"])
    content: str
    theme: str
    document_type: str
    publish_date: date
    embedding: str | None = None


# --------------------------------------------------------------------------- #
# Classe abstraite                                                             #
# --------------------------------------------------------------------------- #

class BaseExtractor(ABC):
    """Interface minimale pour tous les extracteurs."""

    def __init__(self, file_path: str) -> None:
        self.file_path: Path = Path(file_path)

    @abstractmethod
    def extract_many(self, max_length: int = 1_000) -> Iterator[ExtractedDocument]:
        """Yield des `ExtractedDocument` (1 ou n selon le découpage)."""


# --------------------------------------------------------------------------- #
# Split « stream » + disque                                                    #
# --------------------------------------------------------------------------- #

def stream_split_to_disk(
    meta: Dict,
    source: Iterator[str],
    chunk_size: int = 1_500,
    overlap_size: int = 250,
) -> Iterator[ExtractedDocument]:
    """Découpe un flux en chunks *chunk_size* avec overlap.

    Les chunks sont écrits dans un fichier temporaire pour ne pas
    saturer la RAM (utile pour de très gros PDF).

    Parameters
    ----------
    meta :
        Métadonnées communes (title, theme, publish_date…).
    source :
        Flux de texte (pages PDF, lignes, etc.).
    chunk_size :
        Longueur cible d’un chunk.
    overlap_size :
        Nombre de caractères conservés d’un chunk sur l’autre.

    Yields
    ------
    ExtractedDocument
        Chunk + métadonnées.
    """
    assert 0 < overlap_size < chunk_size, "overlap_size must be < chunk_size"

    buffer = ""
    part = 1

    for segment in source:
        if not segment:
            continue
        buffer += segment

        while len(buffer) >= chunk_size:
            chunk_txt = buffer[:chunk_size]
            yield _build_doc(meta, chunk_txt, part)
            part += 1
            buffer = buffer[chunk_size - overlap_size :]

    if buffer.strip():
        yield _build_doc(meta, buffer, part)


def _build_doc(meta: Dict, text: str, part: int) -> ExtractedDocument:
    """Construit un `ExtractedDocument` et écrit/relit sur disque."""
    filename = _TEMP_DIR / f"chunk_{uuid.uuid4().hex}.txt"
    filename.write_text(text, encoding="utf-8")
    content = filename.read_text(encoding="utf-8")
    filename.unlink(missing_ok=True)

    title = f"{meta['title']} (part {part})" if part > 1 else meta["title"]
    return ExtractedDocument(**meta, title=title, content=content)


# --------------------------------------------------------------------------- #
# Segmentation hiérarchique adaptative                                         #
# --------------------------------------------------------------------------- #

def adaptive_segmentation(
    text: str,
    max_length: int = 500,
    overlap: int = 100,
) -> Tuple[List[Dict], Dict]:
    """Découpe Section → Paragraphe → Chunk.

    Returns
    -------
    tuple
        - Liste des chunks (niveaux 0 → 3)
        - Statistiques (dict)
    """
    chunks: List[Dict] = []
    stats = dict(text_length=len(text), section_count=0,
                 paragraph_count=0, chunk_count=0)

    doc_id = f"tmp_doc_{uuid.uuid4().hex[:8]}"
    chunks.append(_make_chunk(doc_id, 0, text[:1_000], 0, len(text)))

    # ----- Section --------------------------------------------------------- #
    for sec_i, sec in enumerate(_split_sections(text)):
        sec_id = f"tmp_sec_{uuid.uuid4().hex[:8]}"
        sec_content = sec["content"]
        chunks.append(
            _make_chunk(
                sec_id, 1, f'{sec["title"]}\n{sec_content[:500]}',
                sec["start_char"], sec["end_char"], doc_id
            )
        )
        stats["section_count"] += 1

        # ----- Paragraphe -------------------------------------------------- #
        for para in _split_paragraphs(sec_content, offset=sec["start_char"]):
            para_id = f"tmp_para_{uuid.uuid4().hex[:8]}"
            chunks.append(_make_chunk(
                para_id, 2, para["content"],
                para["start_char"], para["end_char"], sec_id
            ))
            stats["paragraph_count"] += 1

            # ----- Chunk --------------------------------------------------- #
            for sub in _split_fixed(para["content"], max_length, overlap,
                                    base_offset=para["start_char"]):
                chunks.append(_make_chunk(
                    f"tmp_chunk_{uuid.uuid4().hex[:8]}",
                    3, sub["content"],
                    sub["start_char"], sub["end_char"], para_id
                ))
                stats["chunk_count"] += 1

    return chunks, stats


# --------------------------------------------------------------------------- #
# Helpers segmentation                                                         #
# --------------------------------------------------------------------------- #

def _make_chunk(
    _id: str,
    level: int,
    content: str,
    start: int,
    end: int,
    parent: str | None = None,
) -> Dict:
    return dict(
        id=_id,
        content=content,
        hierarchy_level=level,
        start_char=start,
        end_char=end,
        parent_id=parent,
    )


# -- split helpers ----------------------------------------------------------- #

_SECTION_PATTERNS = [
    re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE),               # Markdown #
    re.compile(r"^([A-Z].{2,70})\n[=\-]{3,}$", re.MULTILINE),   # Underline
    re.compile(r"^([A-Z][A-Za-z0-9\s\-:,.]{2,70})$", re.MULTILINE),
]


def _split_sections(text: str) -> List[Dict]:
    """Détecte les titres et scinde le texte."""
    matches = [
        (m.group(1) if m.lastindex else m.group(0), m.start(), m.end())
        for p in _SECTION_PATTERNS
        for m in p.finditer(text)
    ]
    matches.sort(key=lambda t: t[1])

    if not matches:
        return [dict(title="Document", content=text,
                     start_char=0, end_char=len(text))]

    sections: List[Dict] = []
    for i, (title, s_start, s_end) in enumerate(matches):
        next_start = matches[i + 1][1] if i + 1 < len(matches) else len(text)
        sections.append(dict(
            title=title.strip(),
            content=text[s_end:next_start].strip(),
            start_char=s_start,
            end_char=next_start,
        ))

    # Intro avant le 1ᵉʳ titre
    if matches[0][1] > 0:
        sections.insert(0, dict(
            title="Introduction",
            content=text[:matches[0][1]].strip(),
            start_char=0,
            end_char=matches[0][1],
        ))
    return sections


def _split_paragraphs(text: str, offset: int = 0) -> List[Dict]:
    paragraphs, pos = [], 0
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        start = text.find(block, pos)
        end = start + len(block)
        paragraphs.append(dict(
            content=block,
            start_char=offset + start,
            end_char=offset + end,
        ))
        pos = end
    return paragraphs


def _split_fixed(
    text: str,
    max_len: int,
    overlap: int,
    base_offset: int = 0,
) -> List[Dict]:
    if len(text) <= max_len:
        return [dict(content=text, start_char=base_offset, end_char=base_offset + len(text))]

    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_len, len(text))
        # évite de couper un mot
        if end < len(text):
            while end > start and text[end] not in " .,;\n":
                end -= 1
        chunk_txt = text[start:end].strip()
        chunks.append(dict(
            content=chunk_txt,
            start_char=base_offset + start,
            end_char=base_offset + end,
        ))
        start = end - overlap
    return chunks


def choose_splitter(file_size: int, mime: str) -> str:
    """Retourne 'stream' ou 'adaptive'."""
    if file_size > THRESHOLD_LARGE:
        return "stream"
    if mime in {"application/pdf", "text/plain"}:
        # PDF scanné ou gros TXT non structuré
        return "stream"
    return "adaptive"    