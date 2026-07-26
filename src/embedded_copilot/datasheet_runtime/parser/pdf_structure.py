from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

import fitz

from embedded_copilot.datasheet_runtime.exceptions import (
    DatasheetDocumentRejected,
)
from embedded_copilot.datasheet_runtime.parser.table import (
    TableStructure,
    detect_tables,
)
from embedded_copilot.datasheet_runtime.security.policy import (
    MAX_EXTRACTED_CHARACTERS,
    MAX_PDF_PAGES,
    MAX_PDF_SIZE_BYTES,
)
from embedded_copilot.file_runtime import FileReference, FileType

_READ_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class PdfPageStructure:
    page_number: int
    text: str
    tables: tuple[TableStructure, ...]


@dataclass(frozen=True, slots=True)
class PdfStructure:
    page_count: int
    pages: tuple[PdfPageStructure, ...]


class PDFStructureParser:
    def parse(
        self,
        stream: BinaryIO,
        *,
        reference: FileReference,
    ) -> PdfStructure:
        if (
            reference.document_type not in {FileType.PDF, FileType.DATASHEET}
            or reference.size_bytes > MAX_PDF_SIZE_BYTES
        ):
            raise DatasheetDocumentRejected()
        payload = _read_payload(stream, expected_size=reference.size_bytes)
        try:
            with fitz.open(stream=payload, filetype="pdf") as document:
                if document.needs_pass:
                    raise DatasheetDocumentRejected()
                page_count = document.page_count
                if page_count < 1 or page_count > MAX_PDF_PAGES:
                    raise DatasheetDocumentRejected()
                pages: list[PdfPageStructure] = []
                character_count = 0
                for index, page in enumerate(document):
                    text = page.get_text("text", sort=True)
                    if not isinstance(text, str):
                        raise DatasheetDocumentRejected()
                    character_count += len(text)
                    if character_count > MAX_EXTRACTED_CHARACTERS:
                        raise DatasheetDocumentRejected()
                    pages.append(
                        PdfPageStructure(
                            page_number=index + 1,
                            text=text,
                            tables=detect_tables(page),
                        )
                    )
                return PdfStructure(
                    page_count=page_count,
                    pages=tuple(pages),
                )
        except DatasheetDocumentRejected:
            raise
        except Exception:
            raise DatasheetDocumentRejected() from None


def _read_payload(stream: BinaryIO, *, expected_size: int) -> bytes:
    if expected_size < 1 or expected_size > MAX_PDF_SIZE_BYTES:
        raise DatasheetDocumentRejected()
    payload = bytearray()
    try:
        while len(payload) < expected_size:
            chunk = stream.read(
                min(_READ_CHUNK_SIZE, expected_size - len(payload))
            )
            if not isinstance(chunk, bytes) or not chunk:
                raise DatasheetDocumentRejected()
            payload.extend(chunk)
        if stream.read(1):
            raise DatasheetDocumentRejected()
    except DatasheetDocumentRejected:
        raise
    except Exception:
        raise DatasheetDocumentRejected() from None
    return bytes(payload)
