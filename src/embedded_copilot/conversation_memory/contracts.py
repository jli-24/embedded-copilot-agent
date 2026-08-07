from __future__ import annotations

import copy
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,127}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,255}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|credential|secret)\s*[:=]"
    r"|bearer\s+|sk-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)


class ConversationContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


def safe_text(value: object, *, field: str, maximum: int = 2048) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    checked = unicodedata.normalize("NFC", value).strip()
    if (
        not checked
        or len(checked) > maximum
        or "\x00" in checked
        or "\n" in checked
        or "\r" in checked
        or _SENSITIVE.search(checked)
    ):
        raise ValueError(f"{field} is unsafe")
    return checked


def identifier(value: object, *, field: str) -> str:
    checked = safe_text(value, field=field, maximum=128)
    if not _IDENTIFIER.fullmatch(checked):
        raise ValueError(f"{field} is invalid")
    return checked


def reference(value: object, *, field: str) -> str:
    checked = safe_text(value, field=field, maximum=256)
    if not _REFERENCE.fullmatch(checked):
        raise ValueError(f"{field} is invalid")
    return checked


class ConversationTurn(ConversationContract):
    turn_id: str
    role: Literal["USER", "ASSISTANT"]
    content_summary: str
    references: tuple[str, ...] = ()

    @field_validator("turn_id", mode="before")
    @classmethod
    def validate_turn_id(cls, value: object) -> str:
        return identifier(value, field="turn_id")

    @field_validator("content_summary", mode="before")
    @classmethod
    def validate_content(cls, value: object) -> str:
        return safe_text(value, field="content_summary")

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        if not isinstance(value, tuple):
            raise ValueError("references must be a tuple")
        return copy.deepcopy(value)

    @field_validator("references")
    @classmethod
    def validate_reference_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(reference(item, field="reference") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("references must be unique")
        return checked


class ConversationSnapshot(ConversationContract):
    project_id: str
    session_id: str
    captured_at: datetime
    turns: tuple[ConversationTurn, ...]

    @field_validator("project_id", "session_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("turns", mode="before")
    @classmethod
    def validate_turns(cls, value: object) -> object:
        if not isinstance(value, tuple):
            raise ValueError("turns must be a tuple")
        return copy.deepcopy(value)

    @field_validator("captured_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("captured_at must use UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_turn_ids(self) -> ConversationSnapshot:
        ids = tuple(turn.turn_id for turn in self.turns)
        if len(ids) != len(set(ids)):
            raise ValueError("turn ids must be unique")
        return self


@runtime_checkable
class ConversationMemoryPort(Protocol):
    def extract(
        self, snapshot: ConversationSnapshot
    ) -> object | None: ...


__all__ = [
    "ConversationContract",
    "ConversationMemoryPort",
    "ConversationSnapshot",
    "ConversationTurn",
    "identifier",
    "reference",
    "safe_text",
]
