"""Immutable AI Runtime contracts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.engineering_events import EngineeringEvent

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+|"
    r"(?:password|credential|secret)\s*[:=])",
    re.IGNORECASE,
)


class _AIContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _safe_text(value: object, *, field: str, maximum: int = 1024) -> str:
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > maximum
        or "\x00" in value
        or _SENSITIVE.search(value)
    ):
        raise ValueError(f"{field} is unsafe")
    return value.strip()


def _reference(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 512
        or any(character in value for character in ("\r", "\n", "\x00"))
        or _SENSITIVE.search(value)
    ):
        raise ValueError("reference is unsafe")
    return value


def _tuple(value: object, *, field: str) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _fingerprint_format(value: object) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


class EngineeringChatContext(_AIContract):
    project_id: str
    project_summary: str
    current_stage: str
    reference_ids: tuple[str, ...]
    decision_summaries: tuple[str, ...]
    workspace_fingerprint: str
    fingerprint: str

    _project_id = field_validator("project_id", mode="before")(
        lambda value: _identifier(value, field="project_id")
    )
    _project_summary = field_validator("project_summary", mode="before")(
        lambda value: _safe_text(value, field="project_summary")
    )
    _current_stage = field_validator("current_stage", mode="before")(
        lambda value: _token(value, field="current_stage")
    )
    _workspace = field_validator("workspace_fingerprint", mode="before")(
        _fingerprint_format
    )
    _fingerprint_value = field_validator("fingerprint", mode="before")(
        _fingerprint_format
    )

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        value = _tuple(value, field="reference_ids")
        references = tuple(_reference(item) for item in value)
        if references != tuple(sorted(references)) or len(references) != len(
            set(references)
        ):
            raise ValueError("reference_ids must be sorted and unique")
        return references

    @field_validator("decision_summaries", mode="before")
    @classmethod
    def validate_decisions(cls, value: object) -> object:
        value = _tuple(value, field="decision_summaries")
        decisions = tuple(_token(item, field="decision_summary") for item in value)
        if decisions != tuple(sorted(decisions)) or len(decisions) != len(
            set(decisions)
        ):
            raise ValueError("decision_summaries must be sorted and unique")
        return decisions

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringChatContext:
        if self.fingerprint != engineering_chat_context_fingerprint(**_values(self)):
            raise ValueError("engineering chat context fingerprint mismatch")
        return self


class KnowledgeEvidenceProjection(_AIContract):
    evidence_id: str
    summary: str
    source_references: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    fingerprint: str

    _evidence_id = field_validator("evidence_id", mode="before")(
        lambda value: _identifier(value, field="evidence_id")
    )
    _summary = field_validator("summary", mode="before")(
        lambda value: _safe_text(value, field="summary")
    )
    _fingerprint_value = field_validator("fingerprint", mode="before")(
        _fingerprint_format
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if type(value) is not float:
            raise ValueError("confidence is invalid")
        return value

    @field_validator("source_references", mode="before")
    @classmethod
    def validate_source_references(cls, value: object) -> object:
        value = _tuple(value, field="source_references")
        references = tuple(_reference(item) for item in value)
        if references != tuple(sorted(references)) or len(references) != len(
            set(references)
        ):
            raise ValueError("source_references must be sorted and unique")
        return references

    @model_validator(mode="after")
    def validate_fingerprint(self) -> KnowledgeEvidenceProjection:
        if self.fingerprint != knowledge_evidence_fingerprint(**_values(self)):
            raise ValueError("knowledge evidence fingerprint mismatch")
        return self


class EngineeringChatRequest(_AIContract):
    request_id: str
    project_id: str
    message: str
    context: EngineeringChatContext
    requested_at: datetime
    fingerprint: str

    _request_id = field_validator("request_id", mode="before")(
        lambda value: _identifier(value, field="request_id")
    )
    _project_id = field_validator("project_id", mode="before")(
        lambda value: _identifier(value, field="project_id")
    )
    _message = field_validator("message", mode="before")(
        lambda value: _safe_text(value, field="message")
    )
    _fingerprint_value = field_validator("fingerprint", mode="before")(
        _fingerprint_format
    )

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_bindings(self) -> EngineeringChatRequest:
        if self.context.project_id != self.project_id:
            raise ValueError("project context binding mismatch")
        if self.fingerprint != engineering_chat_request_fingerprint(**_values(self)):
            raise ValueError("engineering chat request fingerprint mismatch")
        return self


class EngineeringModelRequest(_AIContract):
    request_id: str
    message: str
    context_summaries: tuple[str, ...]
    knowledge: tuple[KnowledgeEvidenceProjection, ...]

    _request_id = field_validator("request_id", mode="before")(
        lambda value: _identifier(value, field="request_id")
    )
    _message = field_validator("message", mode="before")(
        lambda value: _safe_text(value, field="message")
    )

    @field_validator("context_summaries", mode="before")
    @classmethod
    def validate_context_summaries(cls, value: object) -> object:
        value = _tuple(value, field="context_summaries")
        return tuple(_safe_text(item, field="context_summary") for item in value)

    @field_validator("knowledge", mode="before")
    @classmethod
    def validate_knowledge(cls, value: object) -> object:
        return _tuple(value, field="knowledge")


class EngineeringModelOutput(_AIContract):
    requirement_analysis: str
    architecture_recommendation: str
    hardware_suggestion: str
    risk_analysis: str
    next_action: str
    reference_ids: tuple[str, ...]
    fingerprint: str

    @field_validator(
        "requirement_analysis",
        "architecture_recommendation",
        "hardware_suggestion",
        "risk_analysis",
        "next_action",
        mode="before",
    )
    @classmethod
    def validate_sections(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        value = _tuple(value, field="reference_ids")
        references = tuple(_reference(item) for item in value)
        if references != tuple(sorted(references)) or len(references) != len(
            set(references)
        ):
            raise ValueError("reference_ids must be sorted and unique")
        return references

    _fingerprint_value = field_validator("fingerprint", mode="before")(
        _fingerprint_format
    )

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringModelOutput:
        if self.fingerprint != engineering_model_output_fingerprint(**_values(self)):
            raise ValueError("engineering model output fingerprint mismatch")
        return self


class EngineeringResponse(_AIContract):
    request_id: str
    project_id: str
    requirement_analysis: str
    architecture_recommendation: str
    hardware_suggestion: str
    risk_analysis: str
    next_action: str
    reference_ids: tuple[str, ...]
    events: tuple[EngineeringEvent, ...]
    fingerprint: str

    _request_id = field_validator("request_id", mode="before")(
        lambda value: _identifier(value, field="request_id")
    )
    _project_id = field_validator("project_id", mode="before")(
        lambda value: _identifier(value, field="project_id")
    )
    _fingerprint_value = field_validator("fingerprint", mode="before")(
        _fingerprint_format
    )

    @field_validator(
        "requirement_analysis",
        "architecture_recommendation",
        "hardware_suggestion",
        "risk_analysis",
        "next_action",
        mode="before",
    )
    @classmethod
    def validate_sections(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        value = _tuple(value, field="reference_ids")
        references = tuple(_reference(item) for item in value)
        if references != tuple(sorted(references)) or len(references) != len(
            set(references)
        ):
            raise ValueError("reference_ids must be sorted and unique")
        return references

    @field_validator("events", mode="before")
    @classmethod
    def validate_events(cls, value: object) -> object:
        return _tuple(value, field="events")

    @model_validator(mode="after")
    def validate_bindings(self) -> EngineeringResponse:
        sequences = tuple(item.sequence for item in self.events)
        if sequences != tuple(range(1, len(self.events) + 1)):
            raise ValueError("engineering response event sequence is invalid")
        if self.fingerprint != engineering_response_fingerprint(**_values(self)):
            raise ValueError("engineering response fingerprint mismatch")
        return self


def canonical_ai_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def engineering_chat_context_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringChatContext", values)


def knowledge_evidence_fingerprint(**values: object) -> str:
    return _fingerprint("KnowledgeEvidenceProjection", values)


def engineering_chat_request_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringChatRequest", values)


def engineering_model_output_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringModelOutput", values)


def engineering_response_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringResponse", values)


def _fingerprint(kind: str, values: dict[str, object]) -> str:
    encoded = canonical_ai_json({"kind": kind, **values}).encode("utf-8")
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

