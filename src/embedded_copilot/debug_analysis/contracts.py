from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import canonical_fingerprint, fingerprint, identifier, safe_text, tuple_only


class DebugContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class DebugSourceType(StrEnum):
    BUILD = "BUILD"
    FLASH = "FLASH"
    RUNTIME = "RUNTIME"
    VALIDATION = "VALIDATION"
    HARDWARE = "HARDWARE"


class DebugCategory(StrEnum):
    COMPILE = "COMPILE"
    LINK = "LINK"
    MEMORY = "MEMORY"
    PERIPHERAL = "PERIPHERAL"
    COMMUNICATION = "COMMUNICATION"
    POWER = "POWER"
    TIMING = "TIMING"
    UNKNOWN = "UNKNOWN"


class DebugSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DebugStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    UNVERIFIED = "UNVERIFIED"


class DebugFinding(DebugContract):
    finding_id: str
    project_id: str
    source_type: DebugSourceType
    category: DebugCategory
    severity: DebugSeverity
    summary: str
    evidence_reference: str
    status: DebugStatus
    fingerprint: str

    @field_validator("finding_id", "project_id", "evidence_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "DebugFinding":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("debug finding fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "DebugFinding":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class DebugInputSnapshot(DebugContract):
    project_id: str
    failure_reference: str
    failure_type: str
    safe_summary: str
    evidence_reference: str
    fingerprint: str

    @field_validator(
        "project_id", "failure_reference", "evidence_reference", mode="before"
    )
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("failure_type", "safe_summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "DebugInputSnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("debug input fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "DebugInputSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class DebugAnalysisSnapshot(DebugContract):
    project_id: str
    failure_reference: str
    findings: tuple[DebugFinding, ...] = Field(max_length=128)
    fingerprint: str

    @field_validator("project_id", "failure_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("findings", mode="before")
    @classmethod
    def validate_findings(cls, value: object) -> object:
        return tuple_only(value, field="findings")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "DebugAnalysisSnapshot":
        ids = tuple(item.finding_id for item in self.findings)
        if len(ids) != len(set(ids)) or any(
            item.project_id != self.project_id for item in self.findings
        ):
            raise ValueError("debug finding identity is invalid")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("debug analysis fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "DebugAnalysisSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


@runtime_checkable
class DebugAnalysisPort(Protocol):
    def get_snapshot(self, project_id: str) -> DebugAnalysisSnapshot | None: ...


@runtime_checkable
class DebugAnalyzerPort(Protocol):
    def analyze(self, value: DebugInputSnapshot) -> DebugAnalysisSnapshot: ...


def validate_finding(value: object) -> DebugFinding:
    if type(value) is not DebugFinding:
        raise TypeError("debug finding is invalid")
    return DebugFinding.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_analysis_snapshot(value: object) -> DebugAnalysisSnapshot:
    if type(value) is not DebugAnalysisSnapshot:
        raise TypeError("debug analysis snapshot is invalid")
    return DebugAnalysisSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "DebugAnalysisPort",
    "DebugAnalysisSnapshot",
    "DebugAnalyzerPort",
    "DebugCategory",
    "DebugContract",
    "DebugFinding",
    "DebugInputSnapshot",
    "DebugSeverity",
    "DebugSourceType",
    "DebugStatus",
    "validate_analysis_snapshot",
    "validate_finding",
]
