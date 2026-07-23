from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from embedded_copilot.schemas.result import ContractModel


DebugPlatform = Literal["ESP32", "STM32"]
DebugErrorType = Literal[
    "compile_error",
    "runtime_crash",
    "memory_error",
    "hard_fault",
    "communication_error",
]
DebugSeverity = Literal["info", "warning", "error", "critical"]


def _normalize_string_list(values: object) -> object:
    if not isinstance(values, list):
        return values
    result: list[object] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip() if isinstance(value, str) else value
        if isinstance(candidate, str):
            if not candidate:
                raise ValueError("list values must not be empty")
            key = candidate.casefold()
            if key in seen:
                continue
            seen.add(key)
        result.append(candidate)
    return result


def _reject_duplicate_findings(findings: list[DebugFinding]) -> None:
    identifiers = [finding.id.casefold() for finding in findings]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate debug finding ids are not allowed")


class DebugRequest(ContractModel):
    input: str = Field(min_length=1)
    project_name: str | None = Field(default=None, min_length=1)
    platform: DebugPlatform | None = None
    error_type: DebugErrorType | None = None
    logs: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "input",
        "project_name",
        "platform",
        "error_type",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("logs", mode="before")
    @classmethod
    def normalize_logs(cls, value: object) -> object:
        return _normalize_string_list(value)


class DebugEvidence(ContractModel):
    source: str = Field(min_length=1)
    content: str = Field(min_length=1)
    category: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("source", "content", "category", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class DebugFinding(ContractModel):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: DebugSeverity
    description: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    recommendation: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "id",
        "category",
        "severity",
        "description",
        "recommendation",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value: object) -> object:
        return _normalize_string_list(value)


class DebugPlan(ContractModel):
    project_name: str = Field(min_length=1)
    platform: DebugPlatform | None = None
    error_type: DebugErrorType
    findings: list[DebugFinding] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "project_name",
        "platform",
        "error_type",
        "rationale",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("actions", mode="before")
    @classmethod
    def normalize_actions(cls, value: object) -> object:
        return _normalize_string_list(value)

    @model_validator(mode="after")
    def reject_duplicate_findings(self) -> "DebugPlan":
        _reject_duplicate_findings(self.findings)
        return self


class DebugReport(ContractModel):
    project_name: str = Field(min_length=1)
    platform: DebugPlatform | None = None
    error_type: DebugErrorType
    summary: str = Field(min_length=1)
    findings: list[DebugFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "project_name",
        "platform",
        "error_type",
        "summary",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("recommendations", mode="before")
    @classmethod
    def normalize_recommendations(cls, value: object) -> object:
        return _normalize_string_list(value)

    @model_validator(mode="after")
    def reject_duplicate_findings(self) -> "DebugReport":
        _reject_duplicate_findings(self.findings)
        return self


class DebugValidationResult(ContractModel):
    success: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("errors", "warnings", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _normalize_string_list(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> "DebugValidationResult":
        if self.success and self.errors:
            raise ValueError("successful debug validation cannot contain errors")
        if not self.success and not self.errors:
            raise ValueError("failed debug validation requires at least one error")
        return self
