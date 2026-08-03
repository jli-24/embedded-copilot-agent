from __future__ import annotations

import copy
import re
import unicodedata
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.memory_automation.contracts import (
    MemoryCandidate,
    MemoryType,
)


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|credential|secret)\s*[:=]"
    r"|bearer\s+|sk-[A-Za-z0-9_-]{8,}", re.IGNORECASE
)


class WriterContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class KnowledgeWriteStatus(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    REJECTED = "REJECTED"


def _text(value: object, *, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value).strip()
    if (
        not candidate
        or len(candidate) > maximum
        or "\x00" in candidate
        or _SENSITIVE.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _id(value: object, *, field: str) -> str:
    candidate = _text(value, field=field, maximum=128)
    if not _ID.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


class MarkdownArtifact(WriterContract):
    memory_id: str
    memory_type: MemoryType
    status: str
    layer: str
    tags: tuple[str, ...]
    title: str
    summary: str
    evidence_references: tuple[str, ...]
    relative_path: str
    candidate_fingerprint: str

    @field_validator("memory_id", mode="before")
    @classmethod
    def validate_memory_id(cls, value: object) -> str:
        return _id(value, field="memory_id")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        if value != "APPROVED":
            raise ValueError("artifact must be approved")
        return "APPROVED"

    @field_validator("layer", "title", "summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator("tags", "evidence_references", mode="before")
    @classmethod
    def tuple_only(cls, value: object, info) -> object:
        if not isinstance(value, tuple):
            raise ValueError(f"{info.field_name} must be a tuple")
        return copy.deepcopy(value)

    @field_validator("tags", "evidence_references")
    @classmethod
    def validate_safe_references(
        cls, value: tuple[str, ...], info
    ) -> tuple[str, ...]:
        return tuple(_text(item, field=info.field_name, maximum=256) for item in value)

    @field_validator("candidate_fingerprint", mode="before")
    @classmethod
    def fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
            raise ValueError("candidate_fingerprint is invalid")
        return value

    @field_validator("relative_path", mode="before")
    @classmethod
    def path(cls, value: object) -> str:
        if not isinstance(value, str) or not value.startswith("docs/knowledge/"):
            raise ValueError("artifact path is invalid")
        if "\\" in value or ".." in value or "\x00" in value:
            raise ValueError("artifact path is invalid")
        return value

    @model_validator(mode="after")
    def validate_type_and_status(self) -> "MarkdownArtifact":
        if self.status != "APPROVED":
            raise ValueError("artifact must be approved")
        expected = (
            f"docs/knowledge/{self.memory_id}-"
            f"{self.memory_type.value.lower()}.md"
        )
        if self.relative_path != expected:
            raise ValueError("artifact path is not deterministic")
        return self


class KnowledgeWriteResult(WriterContract):
    status: KnowledgeWriteStatus
    memory_id: str
    event_type: str | None = None
    message: str

    @field_validator("memory_id", mode="before")
    @classmethod
    def validate_id(cls, value: object) -> str:
        return _id(value, field="memory_id")

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, value: object) -> str:
        return _text(value, field="message", maximum=256)


class KnowledgeWriterPort(Protocol):
    def write(self, artifact: MarkdownArtifact) -> KnowledgeWriteResult: ...


def artifact_from_candidate(candidate: MemoryCandidate) -> MarkdownArtifact:
    if type(candidate) is not MemoryCandidate:
        raise TypeError("memory candidate must be a typed projection")
    checked = MemoryCandidate.model_validate(copy.deepcopy(candidate))
    if checked.review_status.value != "APPROVED":
        raise ValueError("memory candidate is not approved")
    filename = f"{checked.memory_id}-{checked.memory_type.value.lower()}.md"
    return MarkdownArtifact(
        memory_id=checked.memory_id,
        memory_type=checked.memory_type,
        status="APPROVED",
        layer=checked.layer,
        tags=checked.tags,
        title=checked.title,
        summary=checked.summary,
        evidence_references=checked.evidence_references,
        relative_path=f"docs/knowledge/{filename}",
        candidate_fingerprint=checked.fingerprint,
    )
