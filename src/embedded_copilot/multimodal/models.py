from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from embedded_copilot.schemas.result import ContractModel


class MultimodalProcessingError(RuntimeError):
    """Raised when a file cannot be processed safely."""


class FileType(StrEnum):
    PDF = "pdf"
    IMAGE = "image"
    CODE = "code"
    TEXT = "text"
    UNKNOWN = "unknown"


class FileDocument(ContractModel):
    """A file descriptor with processor-specific metadata.

    Each ``file_type`` defines and tests its own metadata schema. Metadata must
    not contain secrets, credentials, image bytes, or other sensitive data. A
    later version may migrate stable public metadata contracts to dedicated
    Pydantic models; Phase 1 intentionally keeps ``dict[str, object]``.

    Phase 1 schemas are ``{"page_count": int, "pages": list[PDFPage]}`` for
    PDF, ``{"width": int, "height": int, "format": str, "path": str,
    "analysis_mode": "offline_metadata"}`` for images, and ``{"content":
    str, "encoding": "utf-8"}`` for code and text files.
    """

    filename: str = Field(min_length=1)
    file_type: FileType
    path: str = Field(min_length=1)
    metadata: dict[str, object]
