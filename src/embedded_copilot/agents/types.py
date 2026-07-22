from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from embedded_copilot.schemas.result import ContractModel


class AgentStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class AgentTask(ContractModel):
    task_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    requirement: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("task_id", "task_type", "requirement", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AgentResult(ContractModel):
    """Foundation execution envelope, separate from runtime domain results."""

    agent_name: str = Field(min_length=1)
    status: AgentStatus
    output: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("agent_name", "output", mode="before")
    @classmethod
    def strip_agent_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
