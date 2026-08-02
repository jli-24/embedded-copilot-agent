"""Immutable conversation feedback contracts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.engineering_events import EngineeringEvent

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+|"
    r"(?:password|credential|secret)\s*[:=])",
    re.IGNORECASE,
)


class _FeedbackContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


class FeedbackType(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    QUESTION = "QUESTION"
    CORRECT = "CORRECT"
    APPROVE = "APPROVE"


class UserFeedback(_FeedbackContract):
    feedback_id: str
    session_id: str
    target_agent: str
    feedback_type: FeedbackType
    message: str
    timestamp: datetime
    fingerprint: str

    @field_validator("feedback_id", "session_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("target_agent", mode="before")
    @classmethod
    def validate_target_agent(cls, value: object) -> str:
        if type(value) is not str or _TOKEN.fullmatch(value) is None:
            raise ValueError("target_agent is invalid")
        return value

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, value: object) -> str:
        if (
            type(value) is not str
            or not value.strip()
            or len(value) > 512
            or any(character in value for character in ("\r", "\n", "\x00"))
            or _SENSITIVE.search(value)
        ):
            raise ValueError("message is unsafe")
        return value.strip()

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
    def validate_fingerprint(self) -> UserFeedback:
        if self.fingerprint != user_feedback_fingerprint(**_values(self)):
            raise ValueError("user feedback fingerprint mismatch")
        return self


class ConversationFeedbackProjection(_FeedbackContract):
    feedback_id: str
    session_id: str
    target_agent: str
    feedback_type: FeedbackType
    event: EngineeringEvent
    fingerprint: str

    @field_validator("feedback_id", "session_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("target_agent", mode="before")
    @classmethod
    def validate_target_agent(cls, value: object) -> str:
        if type(value) is not str or _TOKEN.fullmatch(value) is None:
            raise ValueError("target_agent is invalid")
        return value

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
            raise ValueError("fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def validate_bindings(self) -> ConversationFeedbackProjection:
        if (
            self.event.reference_id != self.feedback_id
            or self.event.timestamp is None
        ):
            raise ValueError("feedback event binding mismatch")
        if self.fingerprint != conversation_feedback_fingerprint(**_values(self)):
            raise ValueError("conversation feedback fingerprint mismatch")
        return self


def canonical_feedback_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def user_feedback_fingerprint(**values: object) -> str:
    return _fingerprint("UserFeedback", values)


def conversation_feedback_fingerprint(**values: object) -> str:
    return _fingerprint("ConversationFeedbackProjection", values)


def _fingerprint(kind: str, values: dict[str, object]) -> str:
    encoded = canonical_feedback_json({"kind": kind, **values}).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


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


def _values(value: BaseModel) -> dict[str, object]:
    return {
        name: getattr(value, name)
        for name in type(value).model_fields
        if name != "fingerprint"
    }

