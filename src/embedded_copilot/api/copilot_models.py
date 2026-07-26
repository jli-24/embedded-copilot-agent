from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from embedded_copilot.conversation.models import ConversationMessage
from embedded_copilot.copilot.models import (
    CopilotContractModel,
    safe_identifier,
    safe_summary,
    utc_datetime,
)
from embedded_copilot.datasheet_runtime import DatasheetSummary
from embedded_copilot.multimodal.context import AttachmentBinding
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)
from embedded_copilot.schemas.result import ContractModel


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
    references: tuple[str, ...] = ()
    created_at: datetime

    @field_validator("message_id", mode="before")
    @classmethod
    def validate_message_id(cls, value: object) -> str:
        return safe_identifier(value, field="message_id")

    @field_validator("content_summary", mode="before")
    @classmethod
    def validate_content_summary(cls, value: object) -> str:
        return safe_summary(value, field="content_summary")

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        from embedded_copilot.copilot.models import identifier_tuple

        return identifier_tuple(value, field="reference")

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="created_at")

    def to_message(self, session_id: str) -> ConversationMessage:
        return ConversationMessage(
            session_id=session_id,
            message_id=self.message_id,
            content_summary=self.content_summary,
            references=self.references,
            created_at=self.created_at,
        )


class CopilotAttachmentRequest(CopilotContractModel):
    reference_id: str
    type: MultimodalInputType
    basename: str
    summary: str
    size_bytes: int = Field(ge=0)
    created_at: datetime

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return safe_identifier(value, field="reference_id")

    @field_validator("type")
    @classmethod
    def validate_type(
        cls,
        value: MultimodalInputType,
    ) -> MultimodalInputType:
        if value is MultimodalInputType.TEXT:
            raise ValueError("attachment type must be IMAGE or FILE")
        return value

    @field_validator("basename", "summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_summary(
            value,
            field=info.field_name,
            max_length=255 if info.field_name == "basename" else 512,
        )

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="created_at")

    def to_binding(self, session_id: str) -> AttachmentBinding:
        return AttachmentBinding(
            session_id=session_id,
            input=MultimodalInput(
                type=self.type,
                reference_id=self.reference_id,
                summary=self.summary,
            ),
            basename=self.basename,
            size_bytes=self.size_bytes,
            created_at=self.created_at,
        )


class CopilotAttachmentReceipt(CopilotContractModel):
    session_id: str
    reference_id: str
    type: MultimodalInputType
    basename: str
    summary: str
    size_bytes: int = Field(ge=0)
    status: Literal["REFERENCED"] = "REFERENCED"
    created_at: datetime

    @classmethod
    def from_binding(
        cls,
        binding: AttachmentBinding,
    ) -> "CopilotAttachmentReceipt":
        return cls(
            session_id=binding.session_id,
            reference_id=binding.input.reference_id,
            type=binding.input.type,
            basename=binding.basename,
            summary=binding.input.summary,
            size_bytes=binding.size_bytes,
            created_at=binding.created_at,
        )


class CopilotVisionRequest(CopilotContractModel):
    reference_id: str
    instruction_summary: str

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return safe_identifier(value, field="reference_id")

    @field_validator("instruction_summary", mode="before")
    @classmethod
    def validate_instruction_summary(cls, value: object) -> str:
        return safe_summary(value, field="instruction_summary")


class CopilotVisionResponse(CopilotContractModel):
    type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    summary: str
    review_required: Literal[True] = True

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_summary(value, field="summary")


class CopilotFileIntelligenceRequest(CopilotContractModel):
    file_id: str
    instruction_summary: str

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, value: object) -> str:
        return safe_identifier(value, field="file_id")

    @field_validator("instruction_summary", mode="before")
    @classmethod
    def validate_instruction_summary(cls, value: object) -> str:
        return safe_summary(value, field="instruction_summary")


class CopilotFileIntelligenceResponse(CopilotContractModel):
    type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    summary: str
    review_required: Literal[True] = True

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_summary(value, field="summary")


class CopilotDatasheetRequest(CopilotContractModel):
    file_id: str
    instruction_summary: str

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, value: object) -> str:
        return safe_identifier(value, field="file_id")

    @field_validator("instruction_summary", mode="before")
    @classmethod
    def validate_instruction_summary(cls, value: object) -> str:
        return safe_summary(value, field="instruction_summary")


class CopilotDatasheetResponse(CopilotContractModel):
    type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    summary: DatasheetSummary
    review_required: Literal[True] = True


class CopilotModelStatusResponse(ContractModel):
    provider: str
    status: Literal["available", "unavailable"]
    capabilities: tuple[str, ...]
    model: str | None
