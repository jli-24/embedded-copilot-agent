from __future__ import annotations

import copy
from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import field_validator

from embedded_copilot.intelligence._validation import (
    safe_identifier,
    safe_text,
    safe_text_tuple,
)
from embedded_copilot.intelligence.models import (
    IntelligenceContractModel,
    ModelResponse,
)


class ConversationIntent(StrEnum):
    ARTIFACT_CHANGE = "ARTIFACT_CHANGE"
    CHAT = "CHAT"
    DEBUG = "DEBUG"
    VISION_ANALYSIS = "VISION_ANALYSIS"
    DATASHEET_ANALYSIS = "DATASHEET_ANALYSIS"
    DESIGN_REVIEW = "DESIGN_REVIEW"
    FIRMWARE = "FIRMWARE"
    KNOWLEDGE = "KNOWLEDGE"
    GENERAL = "GENERAL"


class ConversationMessage(IntelligenceContractModel):
    session_id: str
    message_id: str
    content_summary: str
    references: tuple[str, ...] = ()
    created_at: datetime

    @field_validator("session_id", "message_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("content_summary", mode="before")
    @classmethod
    def validate_content_summary(cls, value: object) -> str:
        return safe_text(value, field="content_summary", max_length=512)

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return value
        isolated = copy.deepcopy(value)
        references = tuple(
            safe_identifier(item, field="reference") for item in isolated
        )
        if len({item.casefold() for item in references}) != len(references):
            raise ValueError("reference must be unique")
        return references

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: object) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() != timedelta(0)
        ):
            raise ValueError("created_at must use UTC")
        return value


class ReasoningOutput(IntelligenceContractModel):
    response: ModelResponse
    reasoning_chain: tuple[str, ...] = ()
    temporary_context: tuple[str, ...] = ()

    @field_validator("response", mode="before")
    @classmethod
    def isolate_response(cls, value: object) -> object:
        return copy.deepcopy(value)

    @field_validator("reasoning_chain", "temporary_context", mode="before")
    @classmethod
    def validate_temporary_text(cls, value: object, info) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return value
        return safe_text_tuple(
            value,
            field=info.field_name,
            max_length=512,
        )


class ConversationTurn(IntelligenceContractModel):
    session_id: str
    intent: ConversationIntent
    answer_summary: str
    handoff: str

    @field_validator("session_id", "handoff", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("answer_summary", mode="before")
    @classmethod
    def validate_answer_summary(cls, value: object) -> str:
        return safe_text(value, field="answer_summary", max_length=512)
