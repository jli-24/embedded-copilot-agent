from __future__ import annotations

from pydantic import Field, field_validator

from embedded_copilot.schemas.result import ContractModel


class DocumentMetadata(ContractModel):
    """Typed, document-specific metadata propagated through the RAG pipeline."""

    chip: str | None = Field(default=None, min_length=1)
    manufacturer: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, min_length=1)
    chapter: str | None = Field(default=None, min_length=1)
    page: int | None = Field(default=None, ge=1)
    document_type: str | None = Field(default=None, min_length=1)

    @field_validator(
        "chip",
        "manufacturer",
        "category",
        "chapter",
        "document_type",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("metadata strings must not be blank")
            return stripped
        return value
