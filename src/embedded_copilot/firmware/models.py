from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from embedded_copilot.schemas.result import ContractModel


class FirmwareRequest(ContractModel):
    requirement: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    framework: str | None = Field(default=None, min_length=1)
    peripherals: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("requirement", "platform", "framework", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("peripherals", mode="before")
    @classmethod
    def normalize_peripherals(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        seen: set[str] = set()
        for item in value:
            candidate = item.strip() if isinstance(item, str) else item
            if isinstance(candidate, str):
                if not candidate:
                    raise ValueError("peripheral names must not be empty")
                key = candidate.casefold()
                if key in seen:
                    continue
                seen.add(key)
            normalized.append(candidate)
        return normalized


class GeneratedFile(ContractModel):
    filename: str = Field(min_length=1)
    content: str
    language: str = Field(min_length=1)

    @field_validator("filename", "language", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GeneratedCode(ContractModel):
    project_name: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    files: list[GeneratedFile] = Field(default_factory=list)

    @field_validator("project_name", "platform", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ValidationResult(ContractModel):
    success: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_outcome(self) -> "ValidationResult":
        if self.success and self.errors:
            raise ValueError("successful validation cannot contain errors")
        if not self.success and not self.errors:
            raise ValueError("failed validation requires at least one error")
        return self
