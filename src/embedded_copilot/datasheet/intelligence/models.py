from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import field_validator

from embedded_copilot.intelligence._validation import (
    safe_identifier,
    safe_text,
    safe_text_tuple,
)
from embedded_copilot.intelligence.models import IntelligenceContractModel


class DatasheetSuggestion(IntelligenceContractModel):
    output_type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    source_reference: str
    chip: str | None = None
    interface: tuple[str, ...] = ()
    pin_reference: tuple[str, ...] = ()
    electrical_reference: tuple[str, ...] = ()
    requires_engineer_review: Literal[True] = True

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_source_reference(cls, value: object) -> str:
        return safe_identifier(value, field="source_reference")

    @field_validator("chip", mode="before")
    @classmethod
    def validate_chip(cls, value: object) -> str | None:
        if value is None:
            return None
        return safe_text(value, field="chip", max_length=256)

    @field_validator(
        "interface",
        "pin_reference",
        "electrical_reference",
        mode="before",
    )
    @classmethod
    def validate_references(cls, value: object, info) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return value
        return safe_text_tuple(
            value,
            field=info.field_name,
            max_length=256,
        )
