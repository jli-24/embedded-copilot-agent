from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from embedded_copilot.input.classifier import AttachmentClassifier
from embedded_copilot.input.loader import DEFAULT_MAX_ATTACHMENT_SIZE_BYTES
from embedded_copilot.input.models import UnifiedInputContext, UserAttachment
from embedded_copilot.schemas.result import ContractModel
from embedded_copilot.services.analysis import AnalysisCommand
from embedded_copilot.services.execution import ExecutionStatus


AnalysisAgent = Literal["firmware", "hardware", "pcb", "debug"]


class AnalysisOptions(ContractModel):
    required_agents: tuple[AnalysisAgent, ...] = ()

    @field_validator("required_agents")
    @classmethod
    def reject_duplicate_agents(
        cls,
        value: tuple[AnalysisAgent, ...],
    ) -> tuple[AnalysisAgent, ...]:
        if len(value) != len(set(value)):
            raise ValueError("required agents must be unique")
        return value


class AnalyzeRequest(ContractModel):
    request: str = Field(min_length=1, max_length=20_000)
    attachments: tuple[UserAttachment, ...] = Field(default=(), max_length=8)
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)

    @field_validator("request", mode="before")
    @classmethod
    def strip_request(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_attachment_contracts(self) -> "AnalyzeRequest":
        identifiers = [item.id.casefold() for item in self.attachments]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("attachment identifiers must be unique")
        for attachment in self.attachments:
            if attachment.size_bytes > DEFAULT_MAX_ATTACHMENT_SIZE_BYTES:
                raise ValueError("attachment size is invalid")
            classified = AttachmentClassifier.classify(
                attachment.filename,
                attachment.content_type,
            )
            if classified is not attachment.media_type:
                raise ValueError("attachment media type is invalid")
        return self

    def to_command(self) -> AnalysisCommand:
        return AnalysisCommand(
            request=self.request,
            input_context=UnifiedInputContext(attachments=self.attachments),
            required_agents=self.options.required_agents,
        )


class AnalyzeResponse(ContractModel):
    execution_id: str = Field(min_length=1)
    status: Literal[ExecutionStatus.QUEUED] = ExecutionStatus.QUEUED
