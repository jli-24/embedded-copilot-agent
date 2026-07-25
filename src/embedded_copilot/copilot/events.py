from __future__ import annotations

from datetime import datetime

from pydantic import field_validator

from embedded_copilot.copilot.models import (
    ApprovalAction,
    CopilotContractModel,
    safe_identifier,
    safe_optional_summary,
    utc_datetime,
)
from embedded_copilot.schemas.knowledge_trace import KnowledgeTrace as KnowledgeTrace


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
