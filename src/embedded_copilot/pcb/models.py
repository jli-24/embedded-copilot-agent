from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from embedded_copilot.schemas.result import ContractModel


def _strip_and_deduplicate(values: object) -> object:
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


def _deduplicate_issues(values: object) -> object:
    if not isinstance(values, list):
        return values
    result: list[object] = []
    seen: set[str] = set()
    for value in values:
        issue_id = value.id if isinstance(value, PCBIssue) else None
        if isinstance(value, dict):
            issue_id = value.get("id")
        if isinstance(issue_id, str):
            key = issue_id.strip().casefold()
            if key in seen:
                continue
            seen.add(key)
        result.append(value)
    return result


class PCBRequirement(ContractModel):
    project_name: str = Field(min_length=1)
    platform: str | None = Field(default=None, min_length=1)
    components: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

    @field_validator("project_name", "platform", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("components", "interfaces", "constraints", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _strip_and_deduplicate(value)


class PCBIssue(ContractModel):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    description: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
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
        return _strip_and_deduplicate(value)


class PCBRuleEvaluation(ContractModel):
    issues: list[PCBIssue] = Field(default_factory=list)
    passed_rules: list[str] = Field(default_factory=list)

    @field_validator("issues", mode="before")
    @classmethod
    def normalize_issues(cls, value: object) -> object:
        return _deduplicate_issues(value)

    @field_validator("passed_rules", mode="before")
    @classmethod
    def normalize_passed_rules(cls, value: object) -> object:
        return _strip_and_deduplicate(value)


class PCBReviewReport(ContractModel):
    project_name: str = Field(min_length=1)
    platform: str | None = Field(default=None, min_length=1)
    issues: list[PCBIssue] = Field(default_factory=list)
    passed_rules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("project_name", "platform", "summary", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("issues", mode="before")
    @classmethod
    def normalize_issues(cls, value: object) -> object:
        return _deduplicate_issues(value)

    @field_validator("passed_rules", "warnings", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _strip_and_deduplicate(value)


class PCBValidationResult(ContractModel):
    success: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("errors", "warnings", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _strip_and_deduplicate(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> "PCBValidationResult":
        if self.success and self.errors:
            raise ValueError("successful PCB validation cannot contain errors")
        if not self.success and not self.errors:
            raise ValueError("failed PCB validation requires at least one error")
        return self
