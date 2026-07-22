from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable

from embedded_copilot.knowledge.models import DocumentMetadata
from embedded_copilot.rag.loader import LoadedDocument


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    source: str
    filename: str
    page: int | None
    section: str | None
    chunk_index: int
    content_hash: str
    source_checksum: str
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    chunks: list[str] = []
    cursor = 0
    while cursor < len(normalized):
        target_end = min(cursor + chunk_size, len(normalized))
        end = target_end
        if target_end < len(normalized):
            minimum_break = cursor + max(1, chunk_size // 2)
            newline = normalized.rfind("\n", minimum_break, target_end)
            space = normalized.rfind(" ", minimum_break, target_end)
            end = max(newline, space)
            if end < minimum_break:
                end = target_end
        chunk = normalized[cursor:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        cursor = max(cursor + 1, end - overlap)
    return chunks


def _section_title(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            return title or None
    return None


def _chunk_id(document: LoadedDocument, chunk_index: int) -> str:
    key = f"{document.source}|{document.page}|{chunk_index}".encode("utf-8")
    return hashlib.sha256(key).hexdigest()


def split_documents(
    documents: Iterable[LoadedDocument],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")

    chunks: list[DocumentChunk] = []
    for document in documents:
        for chunk_index, text in enumerate(
            _split_text(document.text, chunk_size, chunk_overlap)
        ):
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunks.append(
                DocumentChunk(
                    chunk_id=_chunk_id(document, chunk_index),
                    text=text,
                    source=document.source,
                    filename=document.filename,
                    page=(
                        document.page
                        if document.page is not None
                        else document.metadata.page
                    ),
                    section=_section_title(text),
                    chunk_index=chunk_index,
                    content_hash=content_hash,
                    source_checksum=document.checksum,
                    metadata=document.metadata,
                )
            )
    return chunks
