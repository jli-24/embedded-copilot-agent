from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from embedded_copilot.intelligence._validation import safe_identifier, safe_text
from embedded_copilot.intelligence.models import IntelligenceContractModel
from embedded_copilot.schemas.result import ContractModel


class MultimodalProcessingError(RuntimeError):
    """Raised when a file cannot be processed safely."""


class FileType(StrEnum):
    PDF = "pdf"
    IMAGE = "image"
    CODE = "code"
    TEXT = "text"
    UNKNOWN = "unknown"


class MultimodalInputType(StrEnum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    FILE = "FILE"


class MultimodalInput(IntelligenceContractModel):
    type: MultimodalInputType
    reference_id: str
    summary: str

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return safe_identifier(value, field="reference_id")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", max_length=512)


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
