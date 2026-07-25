from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import ConfigDict, Field, field_validator, model_validator

from embedded_copilot.hardware_design.approval import DesignApprovalStatus
from embedded_copilot.hardware_design.decision import DesignDecisionStatus
from embedded_copilot.schemas.model import (
    ModelInputType as ModelInputType,
    ModelRequest as ModelRequest,
    ModelTaskType as ModelTaskType,
)
from embedded_copilot.schemas.result import ContractModel

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:[^/\s]+/)+)",
    re.IGNORECASE,
)
_SENSITIVE_CONFIGURATION = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|(?:password|credential|secret|provider|model(?:[_ -]?name)?|endpoint"
    r"|base[_ -]?url|temperature|top[_ -]?[pk]|max[_ -]?tokens|seed"
    r"|api[_ -]?version|deployment)\s*[:=]"
    r"|(?:pdf[_ -]?content|source[_ -]?code|binary[_ -]?data)\s*[:=]"
    r"|(?:^|\s)sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)
_SOURCE_CODE = re.compile(
    r"(?:#\s*include\b|\b(?:void|int|char|static)\s+[A-Za-z_]\w*\s*\([^)]*\)\s*\{"
    r"|\bdef\s+[A-Za-z_]\w*\s*\([^)]*\)\s*:"
    r"|\b[A-Za-z_]\w*\s*\([^;\r\n]*\)\s*;)",
    re.IGNORECASE,
)
_CREDENTIAL_TOKEN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)
_BINARY_TOKEN = re.compile(
    r"(?:^|\s)[A-Za-z0-9+/]{7,}={1,2}(?:\s|$)",
)


class CopilotContractModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class DesignStage(StrEnum):
    REQUIREMENT_ANALYSIS = "REQUIREMENT_ANALYSIS"
    KNOWLEDGE_RETRIEVAL = "KNOWLEDGE_RETRIEVAL"
    HARDWARE_DESIGN = "HARDWARE_DESIGN"
    FIRMWARE_ANALYSIS = "FIRMWARE_ANALYSIS"
    DEBUG = "DEBUG"
    REPORT = "REPORT"


class SessionApprovalStatus(StrEnum):
    NONE = "NONE"
    PROPOSED = "PROPOSED"
    REVIEWING = "REVIEWING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ChatRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ApprovalAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_MODIFICATION = "REQUEST_MODIFICATION"


class KnowledgeTraceAction(StrEnum):
    VIEWED = "VIEWED"
    USED = "USED"
    SAVED = "SAVED"


class WorkspaceFileType(StrEnum):
    ARTIFACT = "ARTIFACT"
    SOURCE_CODE = "SOURCE_CODE"
    DATASHEET = "DATASHEET"
    REPORT = "REPORT"
    OTHER = "OTHER"


class WorkspaceFileSource(StrEnum):
    INPUT = "INPUT"
    GENERATED = "GENERATED"
    ENGINEERING_ARTIFACT = "ENGINEERING_ARTIFACT"


class WorkspaceFileStatus(StrEnum):
    UPLOADED = "UPLOADED"
    GENERATED = "GENERATED"
    REFERENCED = "REFERENCED"


class WorkflowProgressStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def safe_identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    candidate = value.strip()
    if not _SAFE_IDENTIFIER.fullmatch(candidate) or _CREDENTIAL_TOKEN.search(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def safe_summary(value: object, *, field: str, max_length: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    candidate = value.strip()
    if (
        not candidate
        or len(candidate) > max_length
        or any(char in candidate for char in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE_CONFIGURATION.search(candidate)
        or _SOURCE_CODE.search(candidate)
        or _CREDENTIAL_TOKEN.search(candidate)
        or _BINARY_TOKEN.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def safe_optional_summary(
    value: object,
    *,
    field: str,
    max_length: int = 512,
) -> str | None:
    if value is None:
        return None
    return safe_summary(value, field=field, max_length=max_length)


def identifier_tuple(value: object, *, field: str) -> object:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return value
    isolated = copy.deepcopy(value)
    normalized = tuple(safe_identifier(item, field=field) for item in isolated)
    if len({item.casefold() for item in normalized}) != len(normalized):
        raise ValueError(f"{field} must be unique")
    return normalized


def summary_tuple(
    value: object,
    *,
    field: str,
    max_length: int = 512,
) -> object:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return value
    isolated = copy.deepcopy(value)
    return tuple(
        safe_summary(item, field=field, max_length=max_length) for item in isolated
    )


def utc_datetime(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")
    return value


class ArtifactEvidenceView(CopilotContractModel):
    evidence_id: str
    source_id: str
    summary: str

    @field_validator("evidence_id", "source_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_summary(value, field="summary")


class ArtifactDecisionView(CopilotContractModel):
    decision_id: str
    decision: str
    reason: str
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    status: DesignDecisionStatus
    evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("decision_id", mode="before")
    @classmethod
    def validate_decision_id(cls, value: object) -> str:
        return safe_identifier(value, field="decision_id")

    @field_validator("decision", "reason", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_summary(value, field=info.field_name)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def validate_evidence_ids(cls, value: object) -> object:
        return identifier_tuple(value, field="evidence_id")


class ArtifactView(CopilotContractModel):
    artifact_id: str
    project_name: str
    target_platform: str
    components: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    evidence: tuple[ArtifactEvidenceView, ...] = ()
    decisions: tuple[ArtifactDecisionView, ...] = ()
    approval_status: DesignApprovalStatus

    @field_validator("artifact_id", mode="before")
    @classmethod
    def validate_artifact_id(cls, value: object) -> str:
        return safe_identifier(value, field="artifact_id")

    @field_validator("project_name", "target_platform", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_summary(value, field=info.field_name)

    @field_validator("components", "limitations", mode="before")
    @classmethod
    def validate_text_collections(cls, value: object, info) -> object:
        return summary_tuple(value, field=info.field_name)

    @field_validator("evidence", "decisions", mode="before")
    @classmethod
    def isolate_nested_views(cls, value: object) -> object:
        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return tuple(copy.deepcopy(value))
        return value

    @model_validator(mode="after")
    def validate_evidence_bindings(self) -> "ArtifactView":
        evidence_ids = tuple(item.evidence_id.casefold() for item in self.evidence)
        decision_ids = tuple(item.decision_id.casefold() for item in self.decisions)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Artifact View evidence identifiers are ambiguous")
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("Artifact View decision identifiers are ambiguous")
        available_evidence = set(evidence_ids)
        if any(
            not {item.casefold() for item in decision.evidence_ids}.issubset(
                available_evidence
            )
            for decision in self.decisions
        ):
            raise ValueError("Artifact View decision evidence is unresolved")
        return self
