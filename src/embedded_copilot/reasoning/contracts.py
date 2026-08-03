from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.engineering_intelligence import (
    EngineeringContextSnapshot,
    EngineeringRecommendation,
    EvidenceSourceType,
)

from .models import (
    canonical_fingerprint,
    checked_identifier_tuple,
    checked_text_tuple,
    confidence,
    fingerprint,
    identifier,
    normalize_text,
    tuple_only,
)


class ReasoningContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ReasoningMode(StrEnum):
    EXPLAIN = "EXPLAIN"
    COMPARE = "COMPARE"
    ANALYZE_RISK = "ANALYZE_RISK"
    GENERATE_PLAN = "GENERATE_PLAN"


class ReasoningEvidenceReference(ReasoningContract):
    reference_id: str
    source_type: EvidenceSourceType

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return identifier(value, field="reference_id")


class ReasoningRequest(ReasoningContract):
    request_id: str
    project_id: str
    recommendation_id: str
    context_fingerprint: str
    evidence_references: tuple[ReasoningEvidenceReference, ...]
    question: str
    reasoning_mode: ReasoningMode
    context_snapshot: EngineeringContextSnapshot
    recommendation: EngineeringRecommendation

    @field_validator("request_id", "project_id", "recommendation_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("context_fingerprint", mode="before")
    @classmethod
    def validate_context_fingerprint(cls, value: object) -> str:
        return fingerprint(value, field="context_fingerprint")

    @field_validator("question", mode="before")
    @classmethod
    def validate_question(cls, value: object) -> str:
        return normalize_text(value, field="question", maximum=512)

    @field_validator("evidence_references", mode="before")
    @classmethod
    def validate_evidence_references(cls, value: object) -> object:
        return tuple_only(value, field="evidence_references")

    @model_validator(mode="after")
    def validate_bindings(self) -> "ReasoningRequest":
        if self.project_id != self.context_snapshot.project_id:
            raise ValueError("request project does not match context")
        if self.recommendation_id != self.recommendation.recommendation_id:
            raise ValueError("request recommendation does not match projection")
        if self.context_fingerprint != self.context_snapshot.context_fingerprint:
            raise ValueError("request context fingerprint does not match snapshot")
        references = tuple(item.reference_id for item in self.evidence_references)
        if len(references) != len(set(references)):
            raise ValueError("evidence references must be unique")
        if set(references) != set(self.recommendation.evidence_refs):
            raise ValueError("evidence references do not match recommendation")
        return self


class ReasoningResponse(ReasoningContract):
    summary: str
    explanation: str
    tradeoffs: tuple[str, ...]
    risks: tuple[str, ...]
    references: tuple[str, ...]
    confidence: float
    fingerprint: str

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return normalize_text(value, field="summary", maximum=2048)

    @field_validator("explanation", mode="before")
    @classmethod
    def validate_explanation(cls, value: object) -> str:
        return normalize_text(value, field="explanation", maximum=4096)

    @field_validator("tradeoffs", "risks", mode="before")
    @classmethod
    def validate_text_fields(cls, value: object, info) -> tuple[str, ...]:
        return checked_text_tuple(
            value,
            field=info.field_name,
            maximum_items=16,
            maximum_length=512,
        )

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> tuple[str, ...]:
        return checked_identifier_tuple(
            value,
            field="reference",
            maximum_items=32,
        )

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_response_fingerprint(cls, value: object) -> str:
        return fingerprint(value, field="fingerprint")

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "ReasoningResponse":
        expected = canonical_fingerprint(self, exclude={"fingerprint"})
        if self.fingerprint != expected:
            raise ValueError("reasoning response fingerprint mismatch")
        return self


class ReasoningPort(Protocol):
    def reason(self, request: ReasoningRequest) -> ReasoningResponse: ...


__all__ = [
    "ReasoningContract",
    "ReasoningEvidenceReference",
    "ReasoningMode",
    "ReasoningPort",
    "ReasoningRequest",
    "ReasoningResponse",
]
