from __future__ import annotations

from pydantic import Field, field_validator

from embedded_copilot.schemas.result import ContractModel


class AgentContext(ContractModel):
    """Request-scoped context reserved for tracing and future collaboration."""

    user_id: str | None = Field(default=None, min_length=1)
    session_id: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("user_id", "session_id", mode="before")
    @classmethod
    def strip_identifiers(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
