from __future__ import annotations

import copy
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import (
    canonical_fingerprint,
    fingerprint,
    identifier,
    safe_text,
    tuple_only,
    utc_datetime,
)


class OptimizationContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class OptimizationCategory(StrEnum):
    POWER = "POWER"
    PERFORMANCE = "PERFORMANCE"
    MEMORY = "MEMORY"
    LATENCY = "LATENCY"
    COMMUNICATION = "COMMUNICATION"
    RELIABILITY = "RELIABILITY"


class OptimizationConfidence(StrEnum):
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    UNVERIFIED = "UNVERIFIED"


class OptimizationStatus(StrEnum):
    IDENTIFIED = "IDENTIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OptimizationTarget(StrEnum):
    FIRMWARE = "FIRMWARE"
    HARDWARE = "HARDWARE"
    BUILD = "BUILD"
    CONFIGURATION = "CONFIGURATION"
    TEST = "TEST"


class OptimizationFinding(OptimizationContract):
    finding_id: str
    category: OptimizationCategory
    target: OptimizationTarget
    current_state: str
    suggested_direction: str
    risk: str
    confidence: OptimizationConfidence
    evidence_reference: str
    status: OptimizationStatus
    fingerprint: str

    @field_validator("finding_id", "evidence_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("current_state", "suggested_direction", "risk", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> OptimizationFinding:
        if self.fingerprint != canonical_fingerprint(
            self, exclude={"fingerprint", "status"}
        ):
            raise ValueError("optimization finding fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> OptimizationFinding:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint", "status"}
        )
        return cls.model_validate(values)


class OptimizationAnalysis(OptimizationContract):
    project_id: str
    findings: tuple[OptimizationFinding, ...] = Field(max_length=128)
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("findings", mode="before")
    @classmethod
    def validate_findings(cls, value: object) -> object:
        return tuple_only(value, field="findings")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> OptimizationAnalysis:
        ids = tuple(item.finding_id for item in self.findings)
        if len(ids) != len(set(ids)):
            raise ValueError("finding ids must be unique")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("optimization analysis fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> OptimizationAnalysis:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class OptimizationApprovalRequest(OptimizationContract):
    finding_id: str
    finding_fingerprint: str
    reviewer: str
    decided_at: datetime

    @field_validator("finding_id", "reviewer", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("finding_fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value, field="finding_fingerprint")

    @field_validator("decided_at", mode="before")
    @classmethod
    def validate_decided_at(cls, value: object) -> datetime:
        return utc_datetime(value)


@runtime_checkable
class OptimizationAnalysisPort(Protocol):
    def get_snapshot(self, project_id: str) -> OptimizationAnalysis | None: ...


@runtime_checkable
class OptimizationApprovalPort(Protocol):
    def approve(self, request: OptimizationApprovalRequest) -> OptimizationFinding: ...
    def reject(self, request: OptimizationApprovalRequest) -> OptimizationFinding: ...


def validate_finding(value: object) -> OptimizationFinding:
    if type(value) is not OptimizationFinding:
        raise TypeError("optimization finding is invalid")
    return OptimizationFinding.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_analysis(value: object) -> OptimizationAnalysis:
    if type(value) is not OptimizationAnalysis:
        raise TypeError("optimization analysis is invalid")
    return OptimizationAnalysis.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "OptimizationAnalysis",
    "OptimizationAnalysisPort",
    "OptimizationApprovalPort",
    "OptimizationApprovalRequest",
    "OptimizationCategory",
    "OptimizationConfidence",
    "OptimizationContract",
    "OptimizationFinding",
    "OptimizationStatus",
    "OptimizationTarget",
    "validate_analysis",
    "validate_finding",
]
