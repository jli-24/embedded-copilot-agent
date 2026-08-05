from __future__ import annotations

import copy
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.debug_analysis.contracts import DebugFinding
from embedded_copilot.debug_analysis.models import (
    canonical_fingerprint,
    fingerprint,
    identifier,
    safe_text,
)


class OptimizationContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class OptimizationTargetArea(StrEnum):
    FIRMWARE = "FIRMWARE"
    HARDWARE = "HARDWARE"
    BUILD = "BUILD"
    CONFIGURATION = "CONFIGURATION"
    TEST = "TEST"


class OptimizationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OptimizationConfidence(StrEnum):
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    UNVERIFIED = "UNVERIFIED"


class ReasoningOptimizationProjection(OptimizationContract):
    target_area: OptimizationTargetArea
    suggested_change: str
    reason: str
    evidence_reference: str
    risk: str
    confidence: OptimizationConfidence = OptimizationConfidence.PROJECTED

    @field_validator("suggested_change", "reason", "risk", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("evidence_reference", mode="before")
    @classmethod
    def validate_evidence(cls, value: object) -> str:
        return identifier(value, field="evidence_reference")


class OptimizationProposal(OptimizationContract):
    proposal_id: str
    project_id: str
    target_area: OptimizationTargetArea
    suggested_change: str
    reason: str
    evidence_reference: str
    risk: str
    confidence: OptimizationConfidence
    status: OptimizationStatus
    fingerprint: str

    @field_validator("proposal_id", "project_id", "evidence_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("suggested_change", "reason", "risk", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "OptimizationProposal":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("optimization proposal fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "OptimizationProposal":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class OptimizationApprovalRequest(OptimizationContract):
    proposal_id: str
    proposal_fingerprint: str
    reviewer: str
    decided_at: datetime

    @field_validator("proposal_id", "reviewer", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("proposal_fingerprint", mode="before")
    @classmethod
    def validate_proposal_fingerprint(cls, value: object) -> str:
        return fingerprint(value, field="proposal_fingerprint")

    @field_validator("decided_at", mode="before")
    @classmethod
    def validate_decided_at(cls, value: object) -> datetime:
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("decided_at is invalid") from error
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decided_at must be timezone aware")
        return value.astimezone(timezone.utc)


@runtime_checkable
class OptimizationPort(Protocol):
    def get_snapshot(self, project_id: str) -> OptimizationProposal | None: ...


@runtime_checkable
class OptimizationApprovalPort(Protocol):
    def approve(self, request: OptimizationApprovalRequest) -> OptimizationProposal: ...
    def reject(self, request: OptimizationApprovalRequest) -> OptimizationProposal: ...


@runtime_checkable
class OptimizationReasoningPort(Protocol):
    def project(self, finding: DebugFinding) -> ReasoningOptimizationProjection: ...


def validate_optimization_proposal(value: object) -> OptimizationProposal:
    if type(value) is not OptimizationProposal:
        raise TypeError("optimization proposal is invalid")
    return OptimizationProposal.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "OptimizationApprovalPort",
    "OptimizationApprovalRequest",
    "OptimizationConfidence",
    "OptimizationContract",
    "OptimizationPort",
    "OptimizationProposal",
    "OptimizationReasoningPort",
    "OptimizationStatus",
    "OptimizationTargetArea",
    "ReasoningOptimizationProjection",
    "validate_optimization_proposal",
]
