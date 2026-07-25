from __future__ import annotations

from datetime import datetime

from pydantic import field_validator, model_validator

from embedded_copilot.copilot.models import (
    ChatRole,
    CopilotContractModel,
    DesignStage,
    SessionApprovalStatus,
    identifier_tuple,
    safe_identifier,
    safe_summary,
    utc_datetime,
)


class DesignSessionContext(CopilotContractModel):
    session_id: str
    project_name: str
    user_requirement: str
    current_stage: DesignStage = DesignStage.REQUIREMENT_ANALYSIS
    artifact_ids: tuple[str, ...] = ()
    decision_ids: tuple[str, ...] = ()
    file_ids: tuple[str, ...] = ()
    approval_status: SessionApprovalStatus = SessionApprovalStatus.NONE
    created_at: datetime
    updated_at: datetime

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
    def validate_requirement(cls, value: object) -> str:
        return safe_summary(value, field="user_requirement")

    @field_validator("artifact_ids", "decision_ids", "file_ids", mode="before")
    @classmethod
    def validate_reference_ids(cls, value: object, info) -> object:
        return identifier_tuple(value, field=info.field_name)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: object, info) -> datetime:
        return utc_datetime(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_time_order(self) -> "DesignSessionContext":
        if self.updated_at < self.created_at:
            raise ValueError("session update precedes creation")
        return self


class ChatMessage(CopilotContractModel):
    message_id: str
    role: ChatRole
    content_summary: str
    created_at: datetime
    references: tuple[str, ...] = ()

    @field_validator("message_id", mode="before")
    @classmethod
    def validate_message_id(cls, value: object) -> str:
        return safe_identifier(value, field="message_id")

    @field_validator("content_summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_summary(value, field="content_summary")

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="created_at")

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        return identifier_tuple(value, field="reference")
