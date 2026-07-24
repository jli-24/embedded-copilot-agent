from __future__ import annotations

import fitz

from embedded_copilot.datasheet.exceptions import DatasheetParseError
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.datasheet.parser.base import (
    DEFAULT_MAX_DATASHEET_SIZE_BYTES,
    DatasheetSourceResolver,
    read_datasheet_source,
    validate_parser_limit,
)
from embedded_copilot.datasheet.parser.rules import extract_datasheet_model
from embedded_copilot.input.models import UserAttachment


DEFAULT_MAX_PDF_PAGES = 512
DEFAULT_MAX_PDF_TEXT_CHARS = 2_000_000


class PDFDatasheetParser:
    """Parse bounded PDF text lines into structured evidence."""

    def __init__(
        self,
        resolver: DatasheetSourceResolver,
        *,
        max_size_bytes: int = DEFAULT_MAX_DATASHEET_SIZE_BYTES,
        max_pages: int = DEFAULT_MAX_PDF_PAGES,
        max_text_chars: int = DEFAULT_MAX_PDF_TEXT_CHARS,
    ) -> None:
        if not isinstance(resolver, DatasheetSourceResolver):
            raise DatasheetParseError("Datasheet source resolver is invalid")
        self._resolver = resolver
        self._max_size_bytes = validate_parser_limit(max_size_bytes, label="size")
        self._max_pages = validate_parser_limit(max_pages, label="page")
        self._max_text_chars = validate_parser_limit(max_text_chars, label="text")

    def parse(self, attachment: UserAttachment) -> UnifiedDatasheetModel:
        try:
            raw = read_datasheet_source(
                attachment,
                self._resolver,
                suffix=".pdf",
                content_type="application/pdf",
                metadata_format="pdf",
                max_size_bytes=self._max_size_bytes,
            )
            with fitz.open(stream=raw, filetype="pdf") as document:
                if document.page_count <= 0 or document.page_count > self._max_pages:
                    raise ValueError("invalid page count")
                pages: list[str] = []
                total = 0
                for page in document:
                    text = page.get_text("text")
                    total += len(text)
                    if total > self._max_text_chars:
                        raise ValueError("text limit exceeded")
                    pages.append(text)
            extracted = "\n".join(pages)
            if not extracted.strip() or "\x00" in extracted:
                raise ValueError("text is empty")
            return extract_datasheet_model(extracted, source_format="pdf")
        except DatasheetParseError:
            raise
        except Exception:
            raise DatasheetParseError("PDF Datasheet parsing failed") from None
