from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceCitation(ContractModel):
    source: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    chunk_id: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    RETRIEVAL_ERROR = "retrieval_error"
    MODEL_ERROR = "model_error"
    INTERNAL_ERROR = "internal_error"


class ErrorDetail(ContractModel):
    code: ErrorCode
    message: str = Field(min_length=1)
    retryable: bool = False


class ToolStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


ToolData = TypeVar("ToolData")


class ToolResult(ContractModel, Generic[ToolData]):
    status: ToolStatus
    data: ToolData | None = None
    error: ErrorDetail | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "ToolResult[ToolData]":
        if self.status is ToolStatus.SUCCESS and (self.data is None or self.error is not None):
            raise ValueError("successful tool results require data and no error")
        if self.status is ToolStatus.ERROR and (self.error is None or self.data is not None):
            raise ValueError("failed tool results require an error and no data")
        return self


class KnowledgeResult(ContractModel):
    kind: Literal["knowledge"] = "knowledge"
    answer: str = Field(min_length=1)
    sources: list[SourceCitation] = Field(default_factory=list)
    insufficient_context: bool = False


class FirmwareResult(ContractModel):
    kind: Literal["firmware"] = "firmware"
    language: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    code: str
    explanation: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class DebugResult(ContractModel):
    kind: Literal["debug"] = "debug"
    problem_type: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    root_cause: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]
    solution: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ClarificationResult(ContractModel):
    kind: Literal["clarification"] = "clarification"
    question: str = Field(min_length=1)
    missing_context: list[str] = Field(default_factory=list)


AgentResult = Annotated[
    KnowledgeResult | FirmwareResult | DebugResult | ClarificationResult,
    Field(discriminator="kind"),
]
