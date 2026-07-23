from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from embedded_copilot.firmware.knowledge.models import FirmwareDocument


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


class FirmwareChunker:
    def __init__(self, *, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be non-negative and smaller than chunk_size"
            )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk(self, documents: Iterable[FirmwareDocument]) -> list[FirmwareDocument]:
        chunks: list[FirmwareDocument] = []
        for document in documents:
            for chunk_index, content in enumerate(
                _split_text(document.content, self._chunk_size, self._chunk_overlap)
            ):
                chunk_id = hashlib.sha256(
                    f"{document.id}|{chunk_index}|{content}".encode("utf-8")
                ).hexdigest()
                chunks.append(
                    FirmwareDocument(
                        id=chunk_id,
                        title=document.title,
                        platform=document.platform,
                        framework=document.framework,
                        content=content,
                        metadata={
                            **document.metadata,
                            "source_document_id": document.id,
                            "chunk_index": chunk_index,
                        },
                    )
                )
        return chunks
