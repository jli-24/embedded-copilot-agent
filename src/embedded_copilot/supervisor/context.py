from __future__ import annotations

import copy
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeResult
from embedded_copilot.schemas.result import ContractModel


SupervisorTraceStage = Literal[
    "task_parsed",
    "knowledge_query_built",
    "gateway_retrieved",
    "context_built",
    "agent_routed",
    "finished",
]
SupervisorTraceStatus = Literal["success", "error"]


class KnowledgeContext(ContractModel):
    query: KnowledgeQuery
    retrieved_documents: tuple[KnowledgeResult, ...] = ()
    summary: str = Field(min_length=1)

    @field_validator("query", "retrieved_documents", mode="before")
    @classmethod
    def isolate_nested_models(cls, value: object) -> object:
        return copy.deepcopy(value)

    @field_validator("summary", mode="before")
    @classmethod
    def strip_summary(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SupervisorTraceEvent(ContractModel):
    stage: SupervisorTraceStage
    status: SupervisorTraceStatus
    target: str = Field(min_length=1)
    domains: tuple[str, ...] = ()
    count: int = Field(default=0, ge=0)

    @field_validator("stage", "status", "target", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("domains", mode="before")
    @classmethod
    def isolate_domains(cls, value: object) -> object:
        return copy.deepcopy(value)


class ExecutionContext(ContractModel):
    task: AgentTask
    knowledge_context: KnowledgeContext
    trace: tuple[SupervisorTraceEvent, ...] = ()
    execution_id: UUID

    @field_validator("task", "knowledge_context", "trace", mode="before")
    @classmethod
    def isolate_nested_models(cls, value: object) -> object:
        return copy.deepcopy(value)
