from __future__ import annotations

import importlib
from types import ModuleType

from embedded_copilot.datasheet.extensions.real_pdf.extractor import (
    RealDatasheetExtractionError,
    extract_datasheet_model,
)
from embedded_copilot.datasheet.extensions.real_pdf.section import (
    ExtractedPage,
    normalize_page_text,
)
from embedded_copilot.datasheet.models import UnifiedDatasheetModel


MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 512
MAX_PDF_TEXT_CHARS = 2_000_000


class RealPDFParseError(RuntimeError):
    """Safe error for unsupported or ambiguous real PDF input."""


class RealPDFBackendUnavailable(RealPDFParseError):
    """Raised when the optional text-layer backend is unavailable."""


class RealPDFDatasheetParser:
    def __init__(self, *, backend: ModuleType | None = None) -> None:
        self._backend = backend

    def parse(self, raw_pdf: bytes, *, source_id: str) -> UnifiedDatasheetModel:
        if not isinstance(raw_pdf, bytes) or not raw_pdf or len(raw_pdf) > MAX_PDF_BYTES:
            raise RealPDFParseError("Real PDF Datasheet input is invalid")
        backend = self._backend or self._load_backend()
        try:
            with backend.open(stream=raw_pdf, filetype="pdf") as document:
                if (
                    document.page_count <= 0
                    or document.page_count > MAX_PDF_PAGES
                    or bool(document.needs_pass)
                ):
                    raise ValueError("unsupported document")
                pages: list[ExtractedPage] = []
                total = 0
                for number, page in enumerate(document, start=1):
                    text = normalize_page_text(page.get_text("text"))
                    total += len(text)
                    if total > MAX_PDF_TEXT_CHARS:
                        raise ValueError("text limit exceeded")
                    pages.append(ExtractedPage(number=number, text=text))
            return extract_datasheet_model(tuple(pages), source_id=source_id)
        except RealDatasheetExtractionError:
            raise RealPDFParseError("Real PDF Datasheet extraction failed") from None
        except RealPDFParseError:
            raise
        except Exception:
            raise RealPDFParseError("Real PDF Datasheet parsing failed") from None

    @staticmethod
    def _load_backend() -> ModuleType:
        try:
            return importlib.import_module("fitz")
        except ModuleNotFoundError:
            raise RealPDFBackendUnavailable(
                "Real PDF Datasheet backend is unavailable"
            ) from None
