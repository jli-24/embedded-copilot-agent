from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from embedded_copilot.copilot.models import (
    ApprovalAction,
    CopilotContractModel,
    KnowledgeTraceAction,
    identifier_tuple,
    safe_identifier,
    safe_optional_summary,
    safe_summary,
    utc_datetime,
)


class ApprovalEvent(CopilotContractModel):
    approval_id: str
    action: ApprovalAction
    comment: str | None = None
    timestamp: datetime

    @field_validator("approval_id", mode="before")
    @classmethod
    def validate_approval_id(cls, value: object) -> str:
        return safe_identifier(value, field="approval_id")

    @field_validator("comment", mode="before")
    @classmethod
    def validate_comment(cls, value: object) -> str | None:
        return safe_optional_summary(value, field="comment")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime:
        return utc_datetime(value, field="timestamp")


class KnowledgeTrace(CopilotContractModel):
    query: str
    source_ids: tuple[str, ...] = ()
    result_count: int = Field(ge=0)
    action: KnowledgeTraceAction

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> str:
        return safe_summary(value, field="query")

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_source_ids(cls, value: object) -> object:
        return identifier_tuple(value, field="source_id")

    @model_validator(mode="after")
    def validate_result_binding(self) -> "KnowledgeTrace":
        if bool(self.source_ids) != bool(self.result_count):
            raise ValueError(
                "result count and source IDs must both be empty or populated"
            )
        if self.result_count < len(self.source_ids):
            raise ValueError("result count cannot be lower than unique source count")
        return self
