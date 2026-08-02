"""Immutable engineering event projections."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")


class _EventContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


class EngineeringEventType(StrEnum):
    PROJECT_STARTED = "PROJECT_STARTED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_PROGRESS = "AGENT_PROGRESS"
    ARTIFACT_CREATED = "ARTIFACT_CREATED"
    WARNING = "WARNING"
    ERROR = "ERROR"
    USER_REQUIRED = "USER_REQUIRED"
    COMPLETED = "COMPLETED"
    USER_FEEDBACK = "USER_FEEDBACK"


class EngineeringEvent(_EventContract):
    sequence: int = Field(ge=1)
    event_type: EngineeringEventType
    stage: str
    status: str
    count: int = Field(ge=0)
    reference_id: str | None = None
    timestamp: datetime
    fingerprint: str

    @field_validator("sequence", "count", mode="before")
    @classmethod
    def validate_integer_fields(cls, value: object, info) -> int:
        if type(value) is not int:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("stage", "status", mode="before")
    @classmethod
    def validate_tokens(cls, value: object, info) -> str:
        if type(value) is not str or _TOKEN.fullmatch(value) is None:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError("reference_id is invalid")
        return value

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
            raise ValueError("fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringEvent:
        values = _model_values(self)
        if self.fingerprint != engineering_event_fingerprint(**values):
            raise ValueError("engineering event fingerprint mismatch")
        return self


def canonical_event_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def engineering_event_fingerprint(**values: object) -> str:
    payload = canonical_event_json(
        {"kind": "EngineeringEvent", **values}
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _model_values(value: BaseModel) -> dict[str, object]:
    return {
        name: getattr(value, name)
        for name in type(value).model_fields
        if name != "fingerprint"
    }

