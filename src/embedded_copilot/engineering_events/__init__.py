from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_FP = re.compile(r"^sha256:[a-f0-9]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,127}$")


class EngineeringEventType(StrEnum):
    MEMORY_CREATED = "MEMORY_CREATED"
    MEMORY_UPDATED = "MEMORY_UPDATED"
    MEMORY_REVIEW_REQUIRED = "MEMORY_REVIEW_REQUIRED"
    INTELLIGENCE_QUERY_STARTED = "INTELLIGENCE_QUERY_STARTED"
    INTELLIGENCE_COMPLETED = "INTELLIGENCE_COMPLETED"
    RECOMMENDATION_CREATED = "RECOMMENDATION_CREATED"


class EngineeringEvent(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    sequence: int = Field(ge=1)
    event_type: EngineeringEventType
    stage: str
    status: str
    count: int = Field(ge=0)
    reference_id: str
    timestamp: datetime
    fingerprint: str

    @field_validator("sequence", "count", mode="before")
    @classmethod
    def strict_ints(cls, value: object) -> int:
        if type(value) is not int:
            raise ValueError("integer field is invalid")
        return value

    @field_validator("stage", "status", "reference_id", mode="before")
    @classmethod
    def safe_text(cls, value: object, info) -> str:
        if not isinstance(value, str) or not value.strip() or any(
            token in value for token in ("\x00", "\n", "\r", "/", "\\")
        ):
            raise ValueError(f"{info.field_name} is invalid")
        text = value.strip()
        if not _ID.fullmatch(text):
            raise ValueError(f"{info.field_name} is invalid")
        return text

    @field_validator("timestamp")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone aware")
        return value.astimezone(UTC)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def fingerprint_format(cls, value: object) -> str:
        if not isinstance(value, str) or not _FP.fullmatch(value):
            raise ValueError("fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "EngineeringEvent":
        payload = self.model_dump(mode="json", exclude={"fingerprint"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        if expected != self.fingerprint:
            raise ValueError("event fingerprint mismatch")
        return self


def build_engineering_event(
    *,
    sequence: int,
    event_type: EngineeringEventType,
    stage: str,
    status: str,
    count: int,
    reference_id: str,
    timestamp: datetime,
) -> EngineeringEvent:
    material = EngineeringEvent.model_construct(
        sequence=sequence,
        event_type=event_type,
        stage=stage,
        status=status,
        count=count,
        reference_id=reference_id,
        timestamp=timestamp,
        fingerprint="sha256:" + "0" * 64,
    )
    payload = material.model_dump(mode="json", exclude={"fingerprint"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return EngineeringEvent.model_validate(
        {**payload, "fingerprint": "sha256:" + hashlib.sha256(encoded).hexdigest()}
    )


__all__ = ["EngineeringEvent", "EngineeringEventType", "build_engineering_event"]
