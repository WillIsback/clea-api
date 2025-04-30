# base.py
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, Iterator, Dict
from pydantic import BaseModel, Field
import tempfile
import os
from pathlib import Path

# This is a temporary directory for storing files
TEMP_DIR = Path(tempfile.gettempdir())
if not TEMP_DIR.exists():
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR = Path(tempfile.gettempdir())


class ExtractedDocument(BaseModel):
    """Schéma commun de sortie pour tous les extracteurs de documents."""

    title: str = Field(..., description="Titre du document")
    content: str = Field(..., description="Contenu brut extrait")
    theme: str = Field(..., description="Thème du document")
    document_type: str = Field(..., description="Type (PDF, DOCX, etc.)")
    publish_date: date = Field(..., description="Date de publication")
    embedding: Optional[str] = Field(
        None, description="Représentation vectorielle (optionnelle)"
    )


class BaseExtractor(ABC):
    def __init__(self, file_path: str):
        self.file_path = file_path

    @abstractmethod
    def extract_many(self, max_length: int = 1000) -> Iterator[ExtractedDocument]: ...


def stream_split_to_disk(
    meta: Dict, source: Iterator[str], max_length: int
) -> Iterator[ExtractedDocument]:
    """
    Split un flux de texte en chunks, les écrit temporairement sur disque,
    puis yield des `ExtractedDocument` construits à partir de ces fichiers.
    Chaque document est numéroté automatiquement dans `title` s'il y a plusieurs parties.
    """
    buffer = ""
    part = 1

    for segment in source:
        if not segment:
            continue
        buffer += segment

        while len(buffer) >= max_length:
            chunk, buffer = buffer[:max_length], buffer[max_length:]
            with tempfile.NamedTemporaryFile(
                mode="w+", delete=False, suffix=".txt"
            ) as tmp:
                tmp.write(chunk)
                tmp.flush()
                path = tmp.name

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            os.remove(path)

            title = f"{meta['title']} (part {part})" if part > 1 else meta["title"]
            yield ExtractedDocument(**{**meta, "title": title, "content": content})
            part += 1

    # Dernier buffer
    if buffer:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as tmp:
            tmp.write(buffer)
            tmp.flush()
            path = tmp.name

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        os.remove(path)

        title = f"{meta['title']} (part {part})" if part > 1 else meta["title"]
        yield ExtractedDocument(**{**meta, "title": title, "content": content})
