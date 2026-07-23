from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from embedded_copilot.schemas.result import ContractModel


class ProjectFile(ContractModel):
    path: str = Field(min_length=1)
    content: str
    language: str = Field(min_length=1)

    @field_validator("path", "language", mode="before")
    @classmethod
    def strip_contract_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class FirmwareProject(ContractModel):
    name: str
    platform: str = Field(min_length=1)
    framework: str | None = Field(default=None, min_length=1)
    files: list[ProjectFile] = Field(default_factory=list)
    structure: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("name", "platform", "framework", mode="before")
    @classmethod
    def strip_contract_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("structure", mode="before")
    @classmethod
    def strip_structure_entries(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [entry.strip() if isinstance(entry, str) else entry for entry in value]


class ProjectValidationResult(ContractModel):
    success: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_outcome(self) -> "ProjectValidationResult":
        if self.success and self.errors:
            raise ValueError("successful project validation cannot contain errors")
        if not self.success and not self.errors:
            raise ValueError("failed project validation requires at least one error")
        return self
