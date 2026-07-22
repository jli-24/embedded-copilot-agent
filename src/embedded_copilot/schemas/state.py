from __future__ import annotations

from enum import StrEnum
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field

from embedded_copilot.schemas.result import AgentResult, ErrorDetail, SourceCitation


class Intent(StrEnum):
    KNOWLEDGE = "knowledge"
    FIRMWARE = "firmware"
    DEBUG = "debug"
    UNKNOWN = "unknown"


class AgentName(StrEnum):
    KNOWLEDGE = "knowledge"
    FIRMWARE = "firmware"
    DEBUG = "debug"


class WorkflowStatus(StrEnum):
    ROUTING = "routing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_CLARIFICATION = "needs_clarification"


class MessageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1)


class AgentState(TypedDict):
    trace_id: str
    user_input: str
    intent: Intent
    selected_agents: list[AgentName]
    messages: list[MessageRecord]
    results: list[AgentResult]
    sources: list[SourceCitation]
    errors: list[ErrorDetail]
    final_answer: str
    status: WorkflowStatus
