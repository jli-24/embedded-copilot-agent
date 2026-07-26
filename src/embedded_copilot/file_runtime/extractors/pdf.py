from __future__ import annotations

from typing import BinaryIO

import fitz

from embedded_copilot.file_runtime.contracts import (
    DocumentSummary,
    FileReference,
    FileType,
)
from embedded_copilot.file_runtime.exceptions import FileRuntimeUnavailable

DEFAULT_MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_PDF_PAGES = 512
_READ_CHUNK_SIZE = 64 * 1024


class PdfExtractor:
    __slots__ = ("_max_pages", "_max_size_bytes")

    def __init__(
        self,
        *,
        max_size_bytes: int = DEFAULT_MAX_PDF_SIZE_BYTES,
        max_pages: int = DEFAULT_MAX_PDF_PAGES,
    ) -> None:
        if (
            isinstance(max_size_bytes, bool)
            or not isinstance(max_size_bytes, int)
            or max_size_bytes < 1
            or isinstance(max_pages, bool)
            or not isinstance(max_pages, int)
            or max_pages < 1
        ):
            raise FileRuntimeUnavailable()
        self._max_size_bytes = max_size_bytes
        self._max_pages = max_pages

    def extract(
        self,
        stream: BinaryIO,
        *,
        reference: FileReference,
    ) -> DocumentSummary:
        if reference.document_type not in {FileType.PDF, FileType.DATASHEET}:
            raise FileRuntimeUnavailable()
        payload = bytearray()
        try:
            while True:
                remaining = self._max_size_bytes + 1 - len(payload)
                if remaining <= 0:
                    raise ValueError("size exceeded")
                chunk = stream.read(min(_READ_CHUNK_SIZE, remaining))
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise ValueError("invalid stream")
                payload.extend(chunk)
                if len(payload) > self._max_size_bytes:
                    raise ValueError("size exceeded")
            with fitz.open(stream=bytes(payload), filetype="pdf") as document:
                page_count = document.page_count
                if page_count < 1 or page_count > self._max_pages:
                    raise ValueError("page count is invalid")
                dict(document.metadata or {})
        except Exception:
            raise FileRuntimeUnavailable() from None
        return DocumentSummary(
            file_id=reference.file_id,
            document_type=reference.document_type,
            page_count=page_count,
        )
