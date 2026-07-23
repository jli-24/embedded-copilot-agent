from __future__ import annotations

import re
from collections.abc import Mapping, Sequence, Set
from enum import StrEnum

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


class KnowledgeSource(StrEnum):
    LOCAL = "LOCAL"
    GITHUB = "GITHUB"
    WEB = "WEB"


_SENSITIVE_KEY_PARTS = ("token", "secret", "credential", "password", "path")
_ABSOLUTE_LOCAL_PATH = re.compile(
    r"^(?:[A-Za-z]:[\\/]|\\\\|/|file://)",
    re.IGNORECASE,
)


def _validate_safe_metadata(value: object) -> object:
    if not isinstance(value, Mapping):
        return value
    _walk_metadata(value)
    return value


def _walk_metadata(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError("knowledge metadata keys must be strings")
            lowered = key.casefold()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                raise ValueError("knowledge metadata contains a forbidden key")
            _walk_metadata(nested)
        return
    if isinstance(value, (Sequence, Set)) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for nested in value:
            _walk_metadata(nested)
        return
    if isinstance(value, str) and _ABSOLUTE_LOCAL_PATH.match(value.strip()):
        raise ValueError("knowledge metadata contains an absolute local path")


def _normalize_sources(value: object) -> object:
    if not isinstance(value, list):
        return value
    result: list[object] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, KnowledgeSource):
            source: object = item
            key = item.value
        elif isinstance(item, str):
            normalized = item.strip().upper()
            try:
                source = KnowledgeSource(normalized)
                key = normalized
            except ValueError:
                source = item
                key = normalized
        else:
            source = item
            key = repr(item)
        if key not in seen:
            seen.add(key)
            result.append(source)
    return result


class KnowledgeResult(ContractModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: KnowledgeSource
    score: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id", "title", "content", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> object:
        return _validate_safe_metadata(value)


class KnowledgeQuery(ContractModel):
    query: str = Field(min_length=1)
    sources: list[KnowledgeSource] = Field(default_factory=list)
    top_k: int = Field(default=4, ge=1, le=100)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        return _normalize_sources(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> object:
        return _validate_safe_metadata(value)
