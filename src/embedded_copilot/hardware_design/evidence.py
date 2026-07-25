from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field, field_validator

from embedded_copilot.hardware_design._validation import (
    HardwareDesignModel,
    safe_identifier,
    safe_text,
)

_SAFE_LOCATION = re.compile(
    r"(?:(?:page|line):[1-9][0-9]*|structured:(?:datasheet|firmware)|retrieval:metadata)"
)


class DesignEvidenceSourceType(StrEnum):
    DATASHEET = "datasheet"
    FIRMWARE = "firmware"
    RAG = "rag"


class DesignEvidence(HardwareDesignModel):
    evidence_id: str
    source_id: str
    source_type: DesignEvidenceSourceType
    location: str
    content_summary: str = Field(max_length=512)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @field_validator("evidence_id", "source_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("location", mode="before")
    @classmethod
    def validate_location(cls, value: object) -> str:
        candidate = safe_text(value, field="location", max_length=80)
        if not _SAFE_LOCATION.fullmatch(candidate):
            raise ValueError("evidence location is invalid")
        return candidate

    @field_validator("content_summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="content_summary", max_length=512)
