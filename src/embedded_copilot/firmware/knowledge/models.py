from __future__ import annotations

from pydantic import Field, field_validator

from embedded_copilot.schemas.result import ContractModel


class FirmwareDocument(ContractModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    framework: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id", "title", "platform", "framework", "content", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
