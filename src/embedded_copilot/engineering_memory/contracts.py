from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,127}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,255}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_UNSAFE = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|https?://|provider|runtime|"
    r"credential|password|secret|token|prompt|cot|raw\s+log|stdout|stderr)",
    re.IGNORECASE,
)


class EngineeringMemoryContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class EngineeringMemoryType(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    ARCHITECTURE = "ARCHITECTURE"
    DECISION = "DECISION"
    INTERFACE = "INTERFACE"
    DEBUG_EXPERIENCE = "DEBUG_EXPERIENCE"
    OPTIMIZATION = "OPTIMIZATION"
    VALIDATION = "VALIDATION"
    TRADEOFF = "TRADEOFF"


def _safe_text(value: object, *, field: str, maximum: int = 2048) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")  # noqa: TRY004
    checked = unicodedata.normalize("NFC", value).strip()
    if (
        not checked
        or len(checked) > maximum
        or "\x00" in checked
        or "\n" in checked
        or "\r" in checked
        or _UNSAFE.search(checked)
    ):
        raise ValueError(f"{field} is unsafe")
    return checked


def _identifier(value: object, *, field: str) -> str:
    checked = _safe_text(value, field=field, maximum=128)
    if not _IDENTIFIER.fullmatch(checked):
        raise ValueError(f"{field} is invalid")
    return checked


def _reference(value: object, *, field: str) -> str:
    checked = _safe_text(value, field=field, maximum=256)
    if not _REFERENCE.fullmatch(checked):
        raise ValueError(f"{field} is invalid")
    return checked


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")
    return value.astimezone(UTC)


def _fingerprint(value: object, *, field: str = "fingerprint") -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
        raise ValueError(f"{field} is invalid")
    return value.strip()


def _tuple_only(value: object, *, field: str) -> object:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")  # noqa: TRY004
    return copy.deepcopy(value)


class ApprovalAudit(EngineeringMemoryContract):
    approval_id: str
    candidate_fingerprint: str
    reviewer: str
    decision: Literal["APPROVED"]
    approved_at: datetime

    @field_validator("approval_id", "reviewer", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("candidate_fingerprint", mode="before")
    @classmethod
    def validate_candidate_fingerprint(cls, value: object) -> str:
        return _fingerprint(value, field="candidate_fingerprint")

    @field_validator("approved_at")
    @classmethod
    def validate_approved_at(cls, value: datetime) -> datetime:
        return _utc(value)


class ApprovedEngineeringMemory(EngineeringMemoryContract):
    memory_id: str
    project_id: str
    source_reference: str
    memory_type: EngineeringMemoryType
    status: Literal["APPROVED"] = "APPROVED"
    summary: str
    decision: str
    reason: str
    confidence: float
    evidence: tuple[str, ...] = ()
    approval_audit: ApprovalAudit
    fingerprint: str

    @field_validator("memory_id", "project_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_source_reference(cls, value: object) -> str:
        return _reference(value, field="source_reference")

    @field_validator("summary", "decision", "reason", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, float):
            raise ValueError("confidence must be a float")  # noqa: TRY004
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("confidence is invalid")
        return value

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence(cls, value: object) -> object:
        return _tuple_only(value, field="evidence")

    @field_validator("evidence")
    @classmethod
    def validate_evidence_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_reference(item, field="evidence") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("evidence references must be unique")
        return tuple(sorted(checked))

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return _fingerprint(value)

    @model_validator(mode="after")
    def validate_fingerprint_binding(self) -> ApprovedEngineeringMemory:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("approved memory fingerprint mismatch")
        if self.approval_audit.candidate_fingerprint == self.fingerprint:
            raise ValueError("approval fingerprint must bind the candidate")
        return self

    @classmethod
    def create(cls, **values: object) -> ApprovedEngineeringMemory:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class EngineeringMemoryQuery(EngineeringMemoryContract):
    project_id: str
    query: str
    memory_type: EngineeringMemoryType | None = None
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return _identifier(value, field="project_id")

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> str:
        return _safe_text(value, field="query", maximum=512)


class EngineeringMemoryRetrievalResult(EngineeringMemoryContract):
    project_id: str
    memories: tuple[ApprovedEngineeringMemory, ...]
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return _identifier(value, field="project_id")

    @field_validator("memories", mode="before")
    @classmethod
    def validate_memories(cls, value: object) -> object:
        return _tuple_only(value, field="memories")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_result_fingerprint(cls, value: object) -> str:
        return _fingerprint(value)

    @model_validator(mode="after")
    def validate_result(self) -> EngineeringMemoryRetrievalResult:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("retrieval fingerprint mismatch")
        if any(item.project_id != self.project_id for item in self.memories):
            raise ValueError("retrieval project binding mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        memories: tuple[ApprovedEngineeringMemory, ...],
    ) -> EngineeringMemoryRetrievalResult:
        provisional = cls.model_construct(
            project_id=project_id,
            memories=memories,
            fingerprint="sha256:" + "0" * 64,
        )
        return cls.model_validate(
            {
                "project_id": project_id,
                "memories": memories,
                "fingerprint": canonical_fingerprint(
                    provisional, exclude={"fingerprint"}
                ),
            }
        )


def canonical_fingerprint(
    value: BaseModel, *, exclude: set[str] | frozenset[str] = frozenset()
) -> str:
    payload = value.model_dump(mode="json", exclude=exclude)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = (
    "ApprovalAudit",
    "ApprovedEngineeringMemory",
    "EngineeringMemoryContract",
    "EngineeringMemoryQuery",
    "EngineeringMemoryRetrievalResult",
    "EngineeringMemoryType",
    "canonical_fingerprint",
)
