from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from embedded_copilot.schemas.result import ContractModel


def _strip_and_deduplicate(values: object) -> object:
    if not isinstance(values, list):
        return values
    normalized: list[object] = []
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
        normalized.append(candidate)
    return normalized


class HardwareRequirement(ContractModel):
    requirement: str = Field(min_length=1)
    project_name: str | None = Field(default=None, min_length=1)
    platform: str | None = Field(default=None, min_length=1)
    mcu: str | None = Field(default=None, min_length=1)
    peripherals: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "requirement",
        "project_name",
        "platform",
        "mcu",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("peripherals", "interfaces", "constraints", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _strip_and_deduplicate(value)


class HardwareComponent(ContractModel):
    name: str
    category: str = Field(min_length=1)
    interface: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("name", "category", "description", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("interface", mode="before")
    @classmethod
    def normalize_interfaces(cls, value: object) -> object:
        return _strip_and_deduplicate(value)


class HardwarePlan(ContractModel):
    project_name: str
    platform: str
    mcu: str
    components: list[HardwareComponent] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    power_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    rationale: str
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("project_name", "platform", "mcu", "rationale", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "interfaces",
        "power_requirements",
        "constraints",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _strip_and_deduplicate(value)


class HardwareValidationResult(ContractModel):
    success: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_outcome(self) -> "HardwareValidationResult":
        if self.success and self.errors:
            raise ValueError("successful hardware validation cannot contain errors")
        if not self.success and not self.errors:
            raise ValueError("failed hardware validation requires at least one error")
        return self
