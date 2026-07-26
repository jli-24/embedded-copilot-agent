from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import field_validator

from embedded_copilot.intelligence._validation import safe_identifier, safe_text
from embedded_copilot.intelligence.models import IntelligenceContractModel


class ImageType(StrEnum):
    SCHEMATIC = "schematic"
    PCB = "pcb"
    DATASHEET = "datasheet"
    DEBUG = "debug"
    UNKNOWN = "unknown"


class VisionRequest(IntelligenceContractModel):
    session_id: str
    reference_id: str
    image_type: ImageType
    instruction_summary: str

    @field_validator("session_id", "reference_id", mode="before")
    @classmethod
    def validate_identifier(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("instruction_summary", mode="before")
    @classmethod
    def validate_instruction_summary(cls, value: object) -> str:
        return safe_text(value, field="instruction_summary", max_length=512)


class VisionResponse(IntelligenceContractModel):
    output_type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    summary: str
    review_required: Literal[True] = True

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", max_length=4096)
