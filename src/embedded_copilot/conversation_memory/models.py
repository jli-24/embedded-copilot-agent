from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import field_validator, model_validator

from .contracts import ConversationContract, identifier, reference, safe_text


class MemoryType(StrEnum):
    DECISION = "DECISION"
    DEBUG_EXPERIENCE = "DEBUG_EXPERIENCE"
    OPTIMIZATION = "OPTIMIZATION"
    ARCHITECTURE = "ARCHITECTURE"
    REQUIREMENT = "REQUIREMENT"
    VALIDATION = "VALIDATION"


class MemoryCandidateStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def _fingerprint_material(value: ConversationMemoryCandidate) -> str:
    data = value.model_dump(mode="json", exclude={"fingerprint"})
    encoded = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class ConversationMemoryCandidate(ConversationContract):
    candidate_id: str
    project_id: str
    source_session: str
    memory_type: MemoryType
    summary: str
    decision: str
    reason: str
    related_reference: str | None
    confidence: float
    status: MemoryCandidateStatus
    captured_at: datetime
    fingerprint: str

    @field_validator("candidate_id", "project_id", "source_session", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("summary", "decision", "reason", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("related_reference", mode="before")
    @classmethod
    def validate_related_reference(cls, value: object) -> object:
        if value is None:
            return None
        return reference(value, field="related_reference")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, float) or not 0.0 <= value <= 1.0:
            raise ValueError("confidence is invalid")
        return value

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("captured_at must use UTC")
        return value

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
            raise ValueError("fingerprint is invalid")
        if any(char not in "0123456789abcdef" for char in value[7:]):
            raise ValueError("fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def validate_bound_fingerprint(self) -> ConversationMemoryCandidate:
        if self.fingerprint != _fingerprint_material(self):
            raise ValueError("candidate fingerprint mismatch")
        return self


__all__ = [
    "ConversationMemoryCandidate",
    "MemoryCandidateStatus",
    "MemoryType",
    "_fingerprint_material",
]
