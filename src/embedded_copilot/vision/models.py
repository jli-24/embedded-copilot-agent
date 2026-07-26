from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from embedded_copilot.intelligence._validation import safe_identifier, safe_text
from embedded_copilot.intelligence.models import IntelligenceContractModel


class VisionSuggestion(IntelligenceContractModel):
    output_type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    summary: str
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    source_reference: str

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", max_length=512)

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_source_reference(cls, value: object) -> str:
        return safe_identifier(value, field="source_reference")
