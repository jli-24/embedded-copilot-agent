from __future__ import annotations

import copy
import re
import unicodedata
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.context_runtime.contracts import (
    DatasheetContext,
    FileContext,
    VisionContext,
)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_CONTEXT_ID = re.compile(r"^context:[a-f0-9]{24}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:[^/\s]+/)+)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|(?:password|credential|secret)\s*[:=]"
    r"|(?:^|\s)sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)
_PROHIBITED_ACTION = re.compile(
    r"\b(?:execute|apply|modify|write|patch|generate|build|flash|"
    r"create[_ -]?patch|apply[_ -]?patch|write[_ -]?workspace|"
    r"open[_ -]?terminal|control[_ -]?vscode|change[_ -]?pid)\b",
    re.IGNORECASE,
)

RiskCategory = Literal[
    "context_completeness",
    "component_identity",
    "interface_compatibility",
    "firmware_configuration",
    "visual_interpretation",
]
RiskSeverity = Literal["low", "medium", "high"]
ReasoningConfidence = Literal["low", "medium", "high"]
RuleSource = Literal["context", "component", "interface", "firmware", "vision"]
GeneratedSection = Literal["summary", "risk", "next_step"]
CapabilityName = Literal[
    "context_analysis",
    "risk_detection",
    "verification_planning",
]


def _normalized_string(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return unicodedata.normalize("NFC", value.strip())


def _identifier(value: object, *, field: str) -> str:
    candidate = _normalized_string(value, field=field)
    if not _SAFE_IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _safe_text(value: object, *, field: str, max_length: int) -> str:
    candidate = _normalized_string(value, field=field)
    if (
        not candidate
        or len(candidate) > max_length
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE_TEXT.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _text_tuple(
    value: object,
    *,
    field: str,
    max_items: int,
    max_length: int,
) -> object:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return value
    copied = copy.deepcopy(value)
    items = tuple(
        _safe_text(item, field=field, max_length=max_length) for item in copied
    )
    if len(items) > max_items or len(set(items)) != len(items):
        raise ValueError(f"{field} is invalid")
    return items


class _ReasoningContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class SourceType(StrEnum):
    FILE = "FILE"
    DATASHEET = "DATASHEET"
    VISION = "VISION"


class ReasoningContextSnapshot(_ReasoningContract):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_fingerprint: str
    context_id: str
    task_intent: str
    reference_ids: tuple[str, ...] = Field(max_length=32)
    source_types: tuple[SourceType, ...] = Field(max_length=32)
    datasheet_candidates: tuple[DatasheetContext, ...] = ()
    file_summaries: tuple[FileContext, ...] = ()
    vision_refs: tuple[VisionContext, ...] = ()

    @field_validator("snapshot_fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        candidate = _normalized_string(value, field="snapshot_fingerprint")
        if not _FINGERPRINT.fullmatch(candidate):
            raise ValueError("snapshot_fingerprint is invalid")
        return candidate

    @field_validator("context_id", mode="before")
    @classmethod
    def validate_context_id(cls, value: object) -> str:
        candidate = _normalized_string(value, field="context_id")
        if not _CONTEXT_ID.fullmatch(candidate):
            raise ValueError("context_id is invalid")
        return candidate

    @field_validator("task_intent", mode="before")
    @classmethod
    def validate_task_intent(cls, value: object) -> str:
        return _safe_text(value, field="task_intent", max_length=512)

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_reference_ids(cls, value: object) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value, (str, bytes, bytearray)
        ):
            return value
        references = tuple(
            _identifier(item, field="reference_id") for item in copy.deepcopy(value)
        )
        if len({item.casefold() for item in references}) != len(references):
            raise ValueError("reference_ids must be unique")
        return references

    @model_validator(mode="after")
    def validate_source_alignment(self) -> "ReasoningContextSnapshot":
        if len(self.reference_ids) != len(self.source_types):
            raise ValueError("snapshot source types are misaligned")
        return self


class ReasoningRequest(_ReasoningContract):
    session_id: str
    trace_id: str
    context_snapshot: ReasoningContextSnapshot

    @field_validator("session_id", "trace_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


class CapabilityEntry(_ReasoningContract):
    name: CapabilityName
    version: Literal["1.0"] = "1.0"


class RuleResult(_ReasoningContract):
    rule_id: str
    rule_version: Literal["1.0"] = "1.0"
    rule_source: RuleSource
    triggered: bool
    references: tuple[str, ...] = Field(max_length=32)
    reason: str

    @field_validator("rule_id", mode="before")
    @classmethod
    def validate_rule_id(cls, value: object) -> str:
        return _identifier(value, field="rule_id")

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value, (str, bytes, bytearray)
        ):
            return value
        references = tuple(
            _identifier(item, field="reference") for item in copy.deepcopy(value)
        )
        if len({item.casefold() for item in references}) != len(references):
            raise ValueError("references must be unique")
        return references

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str:
        return _safe_text(value, field="rule reason", max_length=512)

    @model_validator(mode="after")
    def validate_trigger_references(self) -> "RuleResult":
        if not self.triggered and self.references:
            raise ValueError("inactive rule cannot carry references")
        return self


class SupportingReference(_ReasoningContract):
    reference_id: str
    source_type: SourceType
    reason: str

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return _identifier(value, field="reference_id")

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str:
        return _safe_text(value, field="supporting reason", max_length=512)


class RiskCandidate(_ReasoningContract):
    category: RiskCategory
    description: str
    severity: RiskSeverity
    supporting_references: tuple[SupportingReference, ...] = ()

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> str:
        return _safe_text(value, field="risk description", max_length=512)


class NextStep(_ReasoningContract):
    action: str
    reason: str

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, value: object) -> str:
        action = _safe_text(value, field="next step action", max_length=256)
        if _PROHIBITED_ACTION.search(action):
            raise ValueError("next step action is prohibited")
        return action

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str:
        reason = _safe_text(value, field="next step reason", max_length=512)
        if _PROHIBITED_ACTION.search(reason):
            raise ValueError("next step reason is prohibited")
        return reason


class ReasoningSummary(_ReasoningContract):
    summary: str
    presentation_summary: str | None = None
    confidence: ReasoningConfidence
    assumptions: tuple[str, ...] = Field(max_length=16)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="reasoning summary", max_length=1024)

    @field_validator("presentation_summary", mode="before")
    @classmethod
    def validate_presentation_summary(cls, value: object) -> str | None:
        if value is None:
            return None
        return _safe_text(value, field="presentation summary", max_length=512)

    @field_validator("assumptions", mode="before")
    @classmethod
    def validate_assumptions(cls, value: object) -> object:
        return _text_tuple(
            value,
            field="assumption",
            max_items=16,
            max_length=512,
        )


class ReasoningTrace(_ReasoningContract):
    trace_id: str
    context_id: str
    snapshot_fingerprint: str
    capabilities_applied: tuple[CapabilityEntry, ...] = ()
    rules_applied: tuple[RuleResult, ...] = ()
    generated_sections: tuple[GeneratedSection, ...] = ()

    @field_validator("trace_id", mode="before")
    @classmethod
    def validate_trace_id(cls, value: object) -> str:
        return _identifier(value, field="trace_id")

    @field_validator("context_id", mode="before")
    @classmethod
    def validate_context_id(cls, value: object) -> str:
        candidate = _normalized_string(value, field="context_id")
        if not _CONTEXT_ID.fullmatch(candidate):
            raise ValueError("context_id is invalid")
        return candidate

    @field_validator("snapshot_fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        candidate = _normalized_string(value, field="snapshot_fingerprint")
        if not _FINGERPRINT.fullmatch(candidate):
            raise ValueError("snapshot_fingerprint is invalid")
        return candidate


class ReasoningResponse(_ReasoningContract):
    output_type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    reasoning_summary: ReasoningSummary
    risks: tuple[RiskCandidate, ...] = Field(default=(), max_length=8)
    next_steps: tuple[NextStep, ...] = Field(default=(), max_length=8)
    trace: ReasoningTrace
    review_required: Literal[True] = True
