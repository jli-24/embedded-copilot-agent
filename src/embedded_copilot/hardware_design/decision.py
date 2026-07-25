from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from embedded_copilot.hardware_design._validation import (
    HardwareDesignModel,
    safe_identifier,
    safe_text,
    source_ids,
)


class DesignDecisionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class DesignDecision(HardwareDesignModel):
    decision_id: str
    decision_type: str
    decision: str
    reason: str
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    status: DesignDecisionStatus = DesignDecisionStatus.PROPOSED

    @field_validator("decision_id", mode="before")
    @classmethod
    def validate_identifier(cls, value: object) -> str:
        return safe_identifier(value, field="decision_id")

    @field_validator("decision_type", "decision", "reason", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def validate_evidence_ids(cls, value: object) -> object:
        return source_ids(value)
