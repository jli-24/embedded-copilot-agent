from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,127}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,255}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|credential|secret)\s*[:=]"
    r"|bearer\s+|sk-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)


class MemoryContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class MemoryType(StrEnum):
    CONVERSATION_SUMMARY = "CONVERSATION_SUMMARY"
    USER_FEEDBACK = "USER_FEEDBACK"
    ENGINEERING_EVENT = "ENGINEERING_EVENT"
    BUILD_OBSERVATION = "BUILD_OBSERVATION"
    ENGINEERING_LOOP_RESULT = "ENGINEERING_LOOP_RESULT"
    DEBUG_ANALYSIS_RESULT = "DEBUG_ANALYSIS_RESULT"
    OPTIMIZATION_RESULT = "OPTIMIZATION_RESULT"


class MemoryReviewStatus(StrEnum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MemorySourceKind(StrEnum):
    CONVERSATION_SUMMARY = "CONVERSATION_SUMMARY"
    USER_FEEDBACK = "USER_FEEDBACK"
    ENGINEERING_EVENT = "ENGINEERING_EVENT"
    BUILD_OBSERVATION = "BUILD_OBSERVATION"
    ENGINEERING_LOOP_RESULT = "ENGINEERING_LOOP_RESULT"
    DEBUG_ANALYSIS_RESULT = "DEBUG_ANALYSIS_RESULT"
    OPTIMIZATION_RESULT = "OPTIMIZATION_RESULT"
    UNKNOWN = "UNKNOWN"


MemorySourceType = MemorySourceKind


def _safe(value: object, *, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value).strip()
    if (
        not text
        or len(text) > maximum
        or "\x00" in text
        or "\n" in text
        or "\r" in text
        or _SENSITIVE.search(text)
    ):
        raise ValueError(f"{field} is unsafe")
    return text


def _identifier(value: object, *, field: str) -> str:
    text = _safe(value, field=field, maximum=128)
    if not _IDENTIFIER.fullmatch(text):
        raise ValueError(f"{field} is invalid")
    return text


def _reference(value: object, *, field: str) -> str:
    text = _safe(value, field=field, maximum=256)
    lowered = text.casefold()
    if (
        not _REFERENCE.fullmatch(text)
        or text.startswith(("/", "\\"))
        or lowered in {".env", ".git"}
        or any(token in lowered for token in ("secret", "credential", "password"))
    ):
        raise ValueError(f"{field} is invalid")
    return text


def _fingerprint(value: object, *, field: str = "fingerprint") -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
        raise ValueError(f"{field} is invalid")
    return value.strip()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(UTC)


def _finite_confidence(value: object, *, field: str = "confidence") -> float:
    if isinstance(value, bool) or not isinstance(value, float):
        raise ValueError(f"{field} must be a float")
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} is invalid")
    return value


def _tuple_only(value: object, *, field: str) -> object:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    return copy.deepcopy(value)


def _fingerprint_material(model: BaseModel) -> str:
    data = model.model_dump(mode="json", exclude={"fingerprint"})
    encoded = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class MemorySourceProjection(MemoryContract):
    source_type: MemorySourceKind
    source_id: str
    source_reference: str
    source_fingerprint: str
    observed_at: datetime

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> str:
        return _identifier(value, field="source_id")

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return _reference(value, field="source_reference")

    @field_validator("source_fingerprint", mode="before")
    @classmethod
    def validate_source_fingerprint(cls, value: object) -> str:
        return _fingerprint(value, field="source_fingerprint")

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _utc(value)


class MemoryCandidate(MemoryContract):
    memory_id: str
    memory_type: MemoryType
    source: MemorySourceProjection
    title: str = "Engineering Memory"
    layer: Literal["memory"] = "memory"
    tags: tuple[str, ...] = ()
    summary: str
    evidence_references: tuple[str, ...] = ()
    confidence: float
    review_status: MemoryReviewStatus
    fingerprint: str

    @field_validator("memory_id", mode="before")
    @classmethod
    def validate_memory_id(cls, value: object) -> str:
        return _identifier(value, field="memory_id")

    @field_validator("title", "summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _safe(value, field=info.field_name)

    @field_validator("tags", "evidence_references", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return _tuple_only(value, field=info.field_name)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        tags = tuple(_identifier(item, field="tag") for item in value)
        if len(tags) != len(set(tags)):
            raise ValueError("tags must be unique")
        return tuple(sorted(tags))

    @field_validator("evidence_references")
    @classmethod
    def validate_evidence_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        refs = tuple(_reference(item, field="evidence_reference") for item in value)
        if len(refs) != len(set(refs)):
            raise ValueError("evidence references must be unique")
        return tuple(sorted(refs))

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _finite_confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return _fingerprint(value)

    @model_validator(mode="after")
    def validate_fingerprint_binding(self) -> "MemoryCandidate":
        expected = _fingerprint_material(self)
        if self.fingerprint != expected:
            raise ValueError("memory candidate fingerprint mismatch")
        return self

    @property
    def source_projection(self) -> MemorySourceProjection:
        return self.source


class MemoryApprovalProjection(MemoryContract):
    memory_id: str
    candidate_fingerprint: str
    reviewer: str
    decision: Literal["APPROVED", "REJECTED"]
    reviewed_at: datetime

    @field_validator("memory_id", "reviewer", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("candidate_fingerprint", mode="before")
    @classmethod
    def validate_candidate_fingerprint(cls, value: object) -> str:
        return _fingerprint(value, field="candidate_fingerprint")

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: datetime) -> datetime:
        return _utc(value)


class VersionMemoryInput(MemoryContract):
    source: MemorySourceProjection
    summary: str
    memory_type: MemoryType | None = None
    title: str = "Engineering Memory"
    tags: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    confidence: float = 0.5

    @field_validator("summary", "title", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _safe(value, field=info.field_name)

    @field_validator("tags", "evidence_references", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return _tuple_only(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _finite_confidence(value)


class VersionMemoryProjection(MemoryContract):
    candidates: tuple[MemoryCandidate, ...]
    fingerprint: str

    @field_validator("candidates", mode="before")
    @classmethod
    def validate_candidates(cls, value: object) -> object:
        return _tuple_only(value, field="candidates")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_projection_fingerprint(cls, value: object) -> str:
        return _fingerprint(value)

    @model_validator(mode="after")
    def validate_projection(self) -> "VersionMemoryProjection":
        ids = tuple(item.memory_id for item in self.candidates)
        if len(ids) != len(set(ids)):
            raise ValueError("memory ids must be unique")
        if _fingerprint_material(self) != self.fingerprint:
            raise ValueError("memory projection fingerprint mismatch")
        return self


__all__ = [
    "MemoryCandidate",
    "MemoryContract",
    "MemoryReviewStatus",
    "MemorySourceKind",
    "MemorySourceType",
    "MemorySourceProjection",
    "MemoryType",
    "MemoryApprovalProjection",
    "VersionMemoryInput",
    "VersionMemoryProjection",
    "_fingerprint_material",
]
