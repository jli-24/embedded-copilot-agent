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

from embedded_copilot.engineering_events import EngineeringEvent

_FP = re.compile(r"^sha256:[a-f0-9]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|credential|secret)\s*[:=]"
    r"|bearer\s+|sk-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)
_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/|file://)", re.IGNORECASE)


class IntelligenceContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ContextStage(StrEnum):
    REQUIREMENTS = "REQUIREMENTS"
    HARDWARE_DESIGN = "HARDWARE_DESIGN"
    FIRMWARE_DEVELOPMENT = "FIRMWARE_DEVELOPMENT"
    PCB_DESIGN = "PCB_DESIGN"
    DEBUG = "DEBUG"
    VALIDATION = "VALIDATION"


class EvidenceSourceType(StrEnum):
    DATASHEET = "DATASHEET"
    MEMORY = "MEMORY"
    LOCAL_KNOWLEDGE = "LOCAL_KNOWLEDGE"
    WEB = "WEB"
    UNKNOWN = "UNKNOWN"


class EvidenceTrustBasis(StrEnum):
    VERIFIED = "VERIFIED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    PROJECTED = "PROJECTED"
    UNKNOWN = "UNKNOWN"


class EvidenceAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    INVALID = "INVALID"


def _text(
    value: object, *, field: str, maximum: int = 512, allow_empty: bool = False
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    result = unicodedata.normalize("NFC", value).strip()
    if (
        (not result and not allow_empty)
        or len(result) > maximum
        or any(char in result for char in ("\x00", "\r", "\n"))
        or _SENSITIVE.search(result)
        or _ABSOLUTE.search(result)
    ):
        raise ValueError(f"{field} is unsafe")
    return result


def _identifier(value: object, *, field: str) -> str:
    result = _text(value, field=field, maximum=160)
    if not _ID.fullmatch(result):
        raise ValueError(f"{field} is invalid")
    return result


def _tuple_only(value: object, *, field: str) -> object:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    return copy.deepcopy(value)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(UTC)


def _confidence(value: object) -> float:
    if type(value) is not float or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("confidence is invalid")
    return value


def _fingerprint(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _FP.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value


def _material(model: BaseModel, *, exclude: set[str]) -> dict[str, object]:
    return model.model_dump(mode="json", exclude=exclude)


def canonical_fingerprint(
    value: BaseModel,
    *,
    exclude: set[str] | None = None,
) -> str:
    encoded = json.dumps(
        _material(value, exclude=exclude or set()),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class RequirementProjection(IntelligenceContract):
    requirement_id: str
    summary: str

    @field_validator("requirement_id", mode="before")
    @classmethod
    def validate_id(cls, value: object) -> str:
        return _identifier(value, field="requirement_id")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _text(value, field="summary")


class UserFeedbackProjection(IntelligenceContract):
    feedback_id: str
    summary: str
    observed_at: datetime

    @field_validator("feedback_id", mode="before")
    @classmethod
    def validate_id(cls, value: object) -> str:
        return _identifier(value, field="feedback_id")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _text(value, field="summary")

    @field_validator("observed_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return _utc(value)


class BuildObservationProjection(IntelligenceContract):
    observation_id: str
    status: str
    summary: str
    observed_at: datetime

    @field_validator("observation_id", mode="before")
    @classmethod
    def validate_id(cls, value: object) -> str:
        return _identifier(value, field="observation_id")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        return _identifier(value, field="status")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _text(value, field="summary")

    @field_validator("observed_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return _utc(value)


class MemoryReferenceProjection(IntelligenceContract):
    memory_id: str
    reference_id: str

    @field_validator("memory_id", "reference_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


class DatasheetReferenceProjection(IntelligenceContract):
    session_id: str
    file_id: str
    reference_id: str

    @field_validator("session_id", "file_id", "reference_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


class EngineeringContextInputProjection(IntelligenceContract):
    project_id: str
    project_name: str
    stage: ContextStage
    decision_topic: str
    constraints: tuple[str, ...] = ()
    requirements: tuple[RequirementProjection, ...] = ()
    feedback: tuple[UserFeedbackProjection, ...] = ()
    build_observations: tuple[BuildObservationProjection, ...] = ()
    memory_references: tuple[MemoryReferenceProjection, ...] = ()
    datasheet_references: tuple[DatasheetReferenceProjection, ...] = ()
    events: tuple[EngineeringEvent, ...] = ()

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return _identifier(value, field="project_id")

    @field_validator("project_name", "decision_topic", mode="before")
    @classmethod
    def validate_text_fields(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator(
        "constraints",
        "requirements",
        "feedback",
        "build_observations",
        "memory_references",
        "datasheet_references",
        "events",
        mode="before",
    )
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple_only(value, field=info.field_name)

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        values = tuple(_text(item, field="constraint") for item in value)
        if len(values) != len(set(values)):
            raise ValueError("constraints must be unique")
        return values

    @model_validator(mode="after")
    def validate_unique_references(self) -> "EngineeringContextInputProjection":
        ids = tuple(item.reference_id for item in self.memory_references)
        if len(ids) != len(set(ids)):
            raise ValueError("memory references must be unique")
        ids = tuple(item.reference_id for item in self.datasheet_references)
        if len(ids) != len(set(ids)):
            raise ValueError("datasheet references must be unique")
        return self


class EngineeringContextSnapshot(IntelligenceContract):
    schema_version: Literal["1.0"] = "1.0"
    context_fingerprint: str
    project_id: str
    project_name: str
    stage: ContextStage
    decision_topic: str
    constraints: tuple[str, ...] = ()
    requirements: tuple[RequirementProjection, ...] = ()
    feedback: tuple[UserFeedbackProjection, ...] = ()
    build_observations: tuple[BuildObservationProjection, ...] = ()
    memory_references: tuple[MemoryReferenceProjection, ...] = ()
    datasheet_references: tuple[DatasheetReferenceProjection, ...] = ()
    events: tuple[EngineeringEvent, ...] = ()

    @field_validator("context_fingerprint", mode="before")
    @classmethod
    def validate_context_fingerprint(cls, value: object) -> str:
        return _fingerprint(value, field="context_fingerprint")

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "EngineeringContextSnapshot":
        expected = canonical_fingerprint(self, exclude={"context_fingerprint"})
        if self.context_fingerprint != expected:
            raise ValueError("context fingerprint mismatch")
        return self

    @property
    def fingerprint(self) -> str:
        return self.context_fingerprint


class EvidenceClaim(IntelligenceContract):
    subject: str
    parameter: str
    value: str
    unit: str = ""

    @field_validator("subject", "parameter", mode="before")
    @classmethod
    def validate_name(cls, value: object, info) -> str:
        return _text(value, field=info.field_name, maximum=160)

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> str:
        return _text(value, field="claim value", maximum=256)

    @field_validator("unit", mode="before")
    @classmethod
    def validate_unit(cls, value: object) -> str:
        return _text(value, field="unit", maximum=32, allow_empty=True)


class EngineeringEvidence(IntelligenceContract):
    evidence_id: str
    source_type: EvidenceSourceType
    trust_basis: EvidenceTrustBasis
    summary: str
    reference_id: str
    confidence: float
    source_rank: int = 0
    claim: EvidenceClaim | None = None
    fingerprint: str

    @field_validator("evidence_id", "reference_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _text(value, field="summary")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("source_rank", mode="before")
    @classmethod
    def validate_rank(cls, value: object) -> int:
        if type(value) is not int or value < 0:
            raise ValueError("source_rank is invalid")
        return value

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return _fingerprint(value, field="fingerprint")

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "EngineeringEvidence":
        expected = canonical_fingerprint(self, exclude={"fingerprint"})
        if self.fingerprint != expected:
            raise ValueError("evidence fingerprint mismatch")
        return self

    @property
    def source_reference(self) -> str:
        return self.reference_id

    @property
    def component(self) -> str | None:
        return self.claim.subject if self.claim is not None else None

    @property
    def parameter(self) -> str | None:
        return self.claim.parameter if self.claim is not None else None

    @property
    def value(self) -> str | None:
        return self.claim.value if self.claim is not None else None

    @property
    def unit(self) -> str | None:
        return self.claim.unit if self.claim is not None else None


class EvidenceSourceStatus(IntelligenceContract):
    source_type: EvidenceSourceType
    status: EvidenceAvailability


class EvidenceConflict(IntelligenceContract):
    conflict_id: str
    subject: str
    parameter: str
    unit: str
    evidence_ids: tuple[str, ...]
    values: tuple[str, ...]

    @field_validator("conflict_id", mode="before")
    @classmethod
    def validate_id(cls, value: object) -> str:
        return _identifier(value, field="conflict_id")

    @field_validator("subject", "parameter", "unit", mode="before")
    @classmethod
    def validate_text_fields(cls, value: object, info) -> str:
        return _text(
            value,
            field=info.field_name,
            maximum=160,
            allow_empty=info.field_name == "unit",
        )

    @field_validator("evidence_ids", "values", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple_only(value, field=info.field_name)


class EngineeringKnowledgeContext(IntelligenceContract):
    schema_version: Literal["1.0"] = "1.0"
    evidence: tuple[EngineeringEvidence, ...]
    evidence_refs: tuple[str, ...]
    confidence: float
    conflicts: tuple[EvidenceConflict, ...] = ()
    source_statuses: tuple[EvidenceSourceStatus, ...] = ()
    fingerprint: str

    @field_validator(
        "evidence", "evidence_refs", "conflicts", "source_statuses", mode="before"
    )
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return _tuple_only(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_context_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return _fingerprint(value, field="fingerprint")

    @model_validator(mode="after")
    def verify_context(self) -> "EngineeringKnowledgeContext":
        ids = tuple(item.evidence_id for item in self.evidence)
        if len(ids) != len(set(ids)) or self.evidence_refs != ids:
            raise ValueError("evidence identity is invalid")
        statuses = tuple(item.source_type for item in self.source_statuses)
        if len(statuses) != len(set(statuses)):
            raise ValueError("source statuses must be unique")
        expected = canonical_fingerprint(self, exclude={"fingerprint"})
        if self.fingerprint != expected:
            raise ValueError("knowledge context fingerprint mismatch")
        return self


class EngineeringRecommendation(IntelligenceContract):
    schema_version: Literal["1.0"] = "1.0"
    recommendation_id: str
    title: str
    summary: str
    evidence_refs: tuple[str, ...]
    confidence: float
    risks: tuple[str, ...] = ()
    conflicts: tuple[EvidenceConflict, ...] = ()
    review_required: Literal[True] = True
    fingerprint: str

    @field_validator("recommendation_id", mode="before")
    @classmethod
    def validate_id(cls, value: object) -> str:
        return _identifier(value, field="recommendation_id")

    @field_validator("title", "summary", mode="before")
    @classmethod
    def validate_text_fields(cls, value: object, info) -> str:
        return _text(value, field=info.field_name, maximum=1024)

    @field_validator("evidence_refs", "risks", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple_only(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_rec_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return _fingerprint(value, field="fingerprint")

    @model_validator(mode="after")
    def verify_recommendation(self) -> "EngineeringRecommendation":
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("recommendation evidence references must be unique")
        expected = canonical_fingerprint(self, exclude={"fingerprint"})
        if self.fingerprint != expected:
            raise ValueError("recommendation fingerprint mismatch")
        return self


class EngineeringIntelligenceRequest(IntelligenceContract):
    project_id: str
    question: str
    context_snapshot: EngineeringContextSnapshot

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return _identifier(value, field="project_id")

    @field_validator("question", mode="before")
    @classmethod
    def validate_question(cls, value: object) -> str:
        return _text(value, field="question", maximum=512)

    @model_validator(mode="after")
    def bind_context(self) -> "EngineeringIntelligenceRequest":
        if self.project_id != self.context_snapshot.project_id:
            raise ValueError("request context project mismatch")
        return self


class EngineeringIntelligenceResponse(IntelligenceContract):
    recommendation: EngineeringRecommendation
    knowledge_context: EngineeringKnowledgeContext
    query_fingerprint: str
    event_type: Literal["RECOMMENDATION_CREATED"] = "RECOMMENDATION_CREATED"

    @field_validator("query_fingerprint", mode="before")
    @classmethod
    def validate_query_fp(cls, value: object) -> str:
        return _fingerprint(value, field="query_fingerprint")


__all__ = [
    "BuildObservationProjection",
    "ContextStage",
    "DatasheetReferenceProjection",
    "EngineeringContextInputProjection",
    "EngineeringContextSnapshot",
    "EngineeringEvidence",
    "EngineeringIntelligenceRequest",
    "EngineeringIntelligenceResponse",
    "EngineeringKnowledgeContext",
    "EngineeringRecommendation",
    "EvidenceAvailability",
    "EvidenceClaim",
    "EvidenceConflict",
    "EvidenceSourceStatus",
    "EvidenceSourceType",
    "EvidenceTrustBasis",
    "IntelligenceContract",
    "MemoryReferenceProjection",
    "RequirementProjection",
    "UserFeedbackProjection",
    "canonical_fingerprint",
]
