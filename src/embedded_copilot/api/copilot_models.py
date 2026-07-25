from __future__ import annotations

from datetime import datetime

from pydantic import field_validator

from embedded_copilot.conversation.models import ConversationMessage
from embedded_copilot.copilot.models import (
    CopilotContractModel,
    safe_identifier,
    safe_summary,
    utc_datetime,
)


class CopilotSessionCreateRequest(CopilotContractModel):
    session_id: str
    project_name: str
    user_requirement: str
    created_at: datetime

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        return safe_identifier(value, field="session_id")

    @field_validator("project_name", mode="before")
    @classmethod
    def validate_project_name(cls, value: object) -> str:
        return safe_summary(value, field="project_name", max_length=256)

    @field_validator("user_requirement", mode="before")
    @classmethod
    def validate_user_requirement(cls, value: object) -> str:
        return safe_summary(value, field="user_requirement")

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="created_at")


class CopilotMessageRequest(CopilotContractModel):
    message_id: str
    content_summary: str
    created_at: datetime

    @field_validator("message_id", mode="before")
    @classmethod
    def validate_message_id(cls, value: object) -> str:
        return safe_identifier(value, field="message_id")

    @field_validator("content_summary", mode="before")
    @classmethod
    def validate_content_summary(cls, value: object) -> str:
        return safe_summary(value, field="content_summary")

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="created_at")

    def to_message(self, session_id: str) -> ConversationMessage:
        return ConversationMessage(
            session_id=session_id,
            message_id=self.message_id,
            content_summary=self.content_summary,
            created_at=self.created_at,
        )
