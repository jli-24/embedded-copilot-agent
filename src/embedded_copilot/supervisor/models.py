from __future__ import annotations

import copy

from pydantic import Field, field_validator, model_validator

from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.schemas.result import ContractModel


def _normalize_string_list(values: object) -> object:
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


class SupervisorTask(ContractModel):
    request: str = Field(min_length=1)
    project_name: str | None = Field(default=None, min_length=1)
    required_agents: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    input_context: UnifiedInputContext | None = None

    @field_validator("request", "project_name", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("required_agents", "constraints", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _normalize_string_list(value)

    @field_validator("input_context", mode="before")
    @classmethod
    def isolate_input_context(cls, value: object) -> object:
        return copy.deepcopy(value)


class AgentInvocation(ContractModel):
    agent_name: str = Field(min_length=1)
    task: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("agent_name", "task", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SupervisorPlan(ContractModel):
    project_name: str = Field(min_length=1)
    tasks: list[AgentInvocation] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("project_name", "rationale", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_duplicate_agents(self) -> "SupervisorPlan":
        names = [invocation.agent_name.casefold() for invocation in self.tasks]
        if len(names) != len(set(names)):
            raise ValueError("duplicate agent invocations are not allowed")
        return self


class SupervisorResult(ContractModel):
    project_name: str = Field(min_length=1)
    completed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    results: dict[str, object] = Field(default_factory=dict)
    summary: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("project_name", "summary", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("completed", "failed", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> object:
        return _normalize_string_list(value)

    @model_validator(mode="after")
    def validate_result_membership(self) -> "SupervisorResult":
        completed = {name.casefold() for name in self.completed}
        failed = {name.casefold() for name in self.failed}
        if completed.intersection(failed):
            raise ValueError("completed and failed agents must not overlap")
        expected = completed.union(failed)
        actual = {name.casefold() for name in self.results}
        if expected != actual:
            raise ValueError("result keys must match completed and failed agents")
        return self
