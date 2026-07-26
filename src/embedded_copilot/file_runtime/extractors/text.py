from __future__ import annotations

import codecs
from typing import BinaryIO

from embedded_copilot.file_runtime.contracts import (
    DocumentSummary,
    FileReference,
    FileType,
)
from embedded_copilot.file_runtime.exceptions import FileRuntimeUnavailable

DEFAULT_TEXT_CHUNK_SIZE = 64 * 1024


class TextExtractor:
    __slots__ = ("_chunk_size",)

    def __init__(self, *, chunk_size: int = DEFAULT_TEXT_CHUNK_SIZE) -> None:
        if (
            isinstance(chunk_size, bool)
            or not isinstance(chunk_size, int)
            or chunk_size < 1
        ):
            raise FileRuntimeUnavailable()
        self._chunk_size = chunk_size

    def extract(
        self,
        stream: BinaryIO,
        *,
        reference: FileReference,
    ) -> DocumentSummary:
        if reference.document_type not in {
            FileType.TEXT,
            FileType.SOURCE_CODE,
        }:
            raise FileRuntimeUnavailable()
        decoder = codecs.getincrementaldecoder("utf-8-sig")(errors="strict")
        character_count = 0
        line_count = 0
        saw_character = False
        ended_with_newline = False
        try:
            while True:
                chunk = stream.read(self._chunk_size)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise ValueError("invalid stream")
                text = decoder.decode(chunk, final=False)
                character_count += len(text)
                line_count += text.count("\n")
                if text:
                    saw_character = True
                    ended_with_newline = text.endswith("\n")
            tail = decoder.decode(b"", final=True)
            character_count += len(tail)
            line_count += tail.count("\n")
            if tail:
                saw_character = True
                ended_with_newline = tail.endswith("\n")
        except Exception:
            raise FileRuntimeUnavailable() from None
        if saw_character and not ended_with_newline:
            line_count += 1
        return DocumentSummary(
            file_id=reference.file_id,
            document_type=reference.document_type,
            line_count=line_count,
            character_count=character_count,
        )
