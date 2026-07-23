from __future__ import annotations

from pydantic import Field, field_validator

from embedded_copilot.schemas.result import ContractModel


class PCBRuleDocument(ContractModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id", "title", "category", "content", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
