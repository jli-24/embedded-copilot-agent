from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.verification_agent import (
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    VerificationSubjectType,
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._#-]{0,39}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_DERIVED_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,511}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_CURSOR = re.compile(r"^revision:(0|[1-9][0-9]*):offset:(0|[1-9][0-9]*)$")
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?<![A-Za-z0-9._~-])/[^/\s]+)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+|"
    r"(?:password|credential|secret)\s*[:=]|(?:^|\s)sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


class _EngineeringMemoryContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


class MemoryType(StrEnum):
    BOARD_PROFILE = "BOARD_PROFILE"
    COMPONENT = "COMPONENT"
    PIN_BINDING = "PIN_BINDING"
    INTERFACE_BINDING = "INTERFACE_BINDING"
    POWER_CONSTRAINT = "POWER_CONSTRAINT"
    ENGINEERING_DECISION = "ENGINEERING_DECISION"
    KNOWN_ISSUE = "KNOWN_ISSUE"
    VERIFICATION_HISTORY = "VERIFICATION_HISTORY"


class MemoryStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class MemoryCommandType(StrEnum):
    CREATE_CANDIDATE = "CREATE_CANDIDATE"
    CREATE_REPLACEMENT_CANDIDATE = "CREATE_REPLACEMENT_CANDIDATE"
    APPLY_VERIFICATION = "APPLY_VERIFICATION"
    APPLY_HUMAN_APPROVAL = "APPLY_HUMAN_APPROVAL"
    REVOKE_RECORD = "REVOKE_RECORD"
    GET_VERIFIED_SNAPSHOT = "GET_VERIFIED_SNAPSHOT"
    GET_CANDIDATE_SNAPSHOT = "GET_CANDIDATE_SNAPSHOT"
    GET_HISTORY = "GET_HISTORY"


class MemoryAction(StrEnum):
    READ_VERIFIED_MEMORY = "READ_VERIFIED_MEMORY"
    READ_CANDIDATE_MEMORY = "READ_CANDIDATE_MEMORY"
    READ_MEMORY_HISTORY = "READ_MEMORY_HISTORY"
    CREATE_MEMORY_CANDIDATE = "CREATE_MEMORY_CANDIDATE"
    APPLY_VERIFICATION_EVIDENCE = "APPLY_VERIFICATION_EVIDENCE"
    APPLY_HUMAN_APPROVAL = "APPLY_HUMAN_APPROVAL"
    CREATE_REPLACEMENT_CANDIDATE = "CREATE_REPLACEMENT_CANDIDATE"
    REVOKE_MEMORY_RECORD = "REVOKE_MEMORY_RECORD"


class MemoryPermissionStatus(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class MemoryAuditEventType(StrEnum):
    MEMORY_REQUESTED = "MEMORY_REQUESTED"
    MEMORY_COMPLETED = "MEMORY_COMPLETED"
    MEMORY_REJECTED = "MEMORY_REJECTED"
    MEMORY_FAILED = "MEMORY_FAILED"


class MemoryMutationOutcome(StrEnum):
    CREATED = "CREATED"
    TRANSITIONED = "TRANSITIONED"
    REVOKED = "REVOKED"


class MemorySourceType(StrEnum):
    USER_INPUT = "USER_INPUT"
    DATASHEET_RESULT = "DATASHEET_RESULT"
    CODING_RESULT = "CODING_RESULT"
    DEBUG_SNAPSHOT = "DEBUG_SNAPSHOT"
    TELEMETRY_RESULT = "TELEMETRY_RESULT"
    TOOL_RESULT = "TOOL_RESULT"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    MANUAL_DECISION = "MANUAL_DECISION"


class KnownIssueSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MemorySnapshotType(StrEnum):
    VERIFIED = "VERIFIED"
    CANDIDATE = "CANDIDATE"


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")  # noqa: TRY004
    candidate = unicodedata.normalize("NFC", value.strip())
    if not _IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _safe_text(value: object, *, field: str, max_length: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")  # noqa: TRY004
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > max_length
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE_TEXT.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _safe_reference(value: object, *, field: str) -> str:
    candidate = _safe_text(value, field=field, max_length=160)
    if not _REFERENCE.fullmatch(candidate):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _safe_derived_reference(value: object, *, field: str) -> str:
    candidate = _safe_text(value, field=field, max_length=512)
    if not _DERIVED_REFERENCE.fullmatch(candidate):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(UTC)


def _fingerprint(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
        raise ValueError(f"{field} is invalid")
    return value.strip()


class _MemoryRequestContract(_EngineeringMemoryContract):
    request_id: str
    project_id: str
    memory_id: str
    caller: str
    requested_at: datetime

    @field_validator("request_id", "project_id", "memory_id", "caller", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _utc(value)


class _MemoryWriteRequestContract(_MemoryRequestContract):
    operation_id: str
    expected_revision: int = Field(ge=0)

    @field_validator("operation_id", mode="before")
    @classmethod
    def validate_operation_id(cls, value: object) -> str:
        return _identifier(value, field="operation_id")


class BoardProfileMemory(_EngineeringMemoryContract):
    memory_type: Literal[MemoryType.BOARD_PROFILE] = MemoryType.BOARD_PROFILE
    board_id: str
    board_name: str
    mcu_family: str
    mcu_model: str
    architecture: str

    @field_validator("board_id", mode="before")
    @classmethod
    def validate_board_id(cls, value: object) -> str:
        return _identifier(value, field="board_id")

    @field_validator(
        "board_name", "mcu_family", "mcu_model", "architecture", mode="before"
    )
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name, max_length=160)


class ComponentMemory(_EngineeringMemoryContract):
    memory_type: Literal[MemoryType.COMPONENT] = MemoryType.COMPONENT
    component_reference: str
    component_type: str
    part_number: str
    manufacturer: str
    quantity: int = Field(gt=0, le=100_000)

    @field_validator("component_reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return _identifier(value, field="component_reference")

    @field_validator("component_type", "part_number", "manufacturer", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name, max_length=160)


class PinBindingMemory(_EngineeringMemoryContract):
    memory_type: Literal[MemoryType.PIN_BINDING] = MemoryType.PIN_BINDING
    target_id: str
    pin_id: str
    function: str
    component_reference: str
    interface_reference: str

    @field_validator(
        "target_id",
        "pin_id",
        "function",
        "component_reference",
        "interface_reference",
        mode="before",
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


class InterfaceBindingMemory(_EngineeringMemoryContract):
    memory_type: Literal[MemoryType.INTERFACE_BINDING] = MemoryType.INTERFACE_BINDING
    target_id: str
    interface_id: str
    signal: str
    pin_id: str
    component_reference: str

    @field_validator(
        "target_id",
        "interface_id",
        "signal",
        "pin_id",
        "component_reference",
        mode="before",
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


class PowerConstraintMemory(_EngineeringMemoryContract):
    memory_type: Literal[MemoryType.POWER_CONSTRAINT] = MemoryType.POWER_CONSTRAINT
    supply_id: str
    load_id: str
    minimum_voltage_mv: int = Field(ge=0, le=10_000_000)
    maximum_voltage_mv: int = Field(ge=0, le=10_000_000)
    maximum_current_ma: int | None = Field(default=None, gt=0, le=10_000_000)

    @field_validator("supply_id", "load_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_voltage_range(self) -> PowerConstraintMemory:
        if self.minimum_voltage_mv > self.maximum_voltage_mv:
            raise ValueError("power voltage range is invalid")
        return self


class EngineeringDecisionMemory(_EngineeringMemoryContract):
    memory_type: Literal[MemoryType.ENGINEERING_DECISION] = (
        MemoryType.ENGINEERING_DECISION
    )
    decision_topic: str
    decision: str
    rationale_summary: str

    @field_validator("decision_topic", mode="before")
    @classmethod
    def validate_topic(cls, value: object) -> str:
        return _identifier(value, field="decision_topic")

    @field_validator("decision", "rationale_summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)


class KnownIssueMemory(_EngineeringMemoryContract):
    memory_type: Literal[MemoryType.KNOWN_ISSUE] = MemoryType.KNOWN_ISSUE
    issue_key: str
    title: str
    severity: KnownIssueSeverity
    description_summary: str
    mitigation_summary: str

    @field_validator("issue_key", mode="before")
    @classmethod
    def validate_issue_key(cls, value: object) -> str:
        return _identifier(value, field="issue_key")

    @field_validator(
        "title", "description_summary", "mitigation_summary", mode="before"
    )
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)


class VerificationHistoryMemory(_EngineeringMemoryContract):
    memory_type: Literal[MemoryType.VERIFICATION_HISTORY] = (
        MemoryType.VERIFICATION_HISTORY
    )
    verification_request_id: str
    subject_type: VerificationSubjectType
    verification_status: VerificationStatus
    finding_categories: tuple[str, ...] = Field(default=(), max_length=128)
    confidence_basis: str

    @field_validator("verification_request_id", mode="before")
    @classmethod
    def validate_verification_request_id(cls, value: object) -> str:
        return _safe_reference(value, field="verification_request_id")

    @field_validator("finding_categories", mode="before")
    @classmethod
    def validate_categories(cls, value: object) -> object:
        if not isinstance(value, tuple):
            return value
        categories = tuple(
            _identifier(item, field="finding_category") for item in value
        )
        if len(categories) != len(set(categories)):
            raise ValueError("finding categories must be unique")
        return tuple(sorted(categories))

    @field_validator("confidence_basis", mode="before")
    @classmethod
    def validate_confidence_basis(cls, value: object) -> str:
        return _safe_text(value, field="confidence_basis")


MemoryPayload: TypeAlias = Annotated[
    BoardProfileMemory
    | ComponentMemory
    | PinBindingMemory
    | InterfaceBindingMemory
    | PowerConstraintMemory
    | EngineeringDecisionMemory
    | KnownIssueMemory
    | VerificationHistoryMemory,
    Field(discriminator="memory_type"),
]


class MemoryProvenance(_EngineeringMemoryContract):
    source_type: MemorySourceType
    source_reference: str
    source_revision: str
    created_by: str
    observed_at: datetime

    @field_validator("source_reference", "source_revision", "created_by", mode="before")
    @classmethod
    def validate_references(cls, value: object, info) -> str:
        return _safe_reference(value, field=info.field_name)

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _utc(value)


class MemoryStateTransition(_EngineeringMemoryContract):
    from_status: MemoryStatus | None
    to_status: MemoryStatus
    request_id: str
    operation_id: str
    evidence_type: Literal["CREATED", "VERIFICATION", "HUMAN_APPROVAL", "REVOCATION"]
    evidence_reference: str
    reason_code: str
    transitioned_at: datetime

    @field_validator(
        "request_id", "operation_id", "evidence_reference", "reason_code", mode="before"
    )
    @classmethod
    def validate_references(cls, value: object, info) -> str:
        return _safe_reference(value, field=info.field_name)

    @field_validator("transitioned_at")
    @classmethod
    def validate_transitioned_at(cls, value: datetime) -> datetime:
        return _utc(value)


class VerificationEvidenceBinding(_EngineeringMemoryContract):
    verification_request_id: str
    subject_type: VerificationSubjectType
    result_status: VerificationStatus
    request_fingerprint: str
    result_fingerprint: str
    requested_at: datetime
    summary_reference: str

    @field_validator("verification_request_id", "summary_reference", mode="before")
    @classmethod
    def validate_references(cls, value: object, info) -> str:
        return _safe_reference(value, field=info.field_name)

    @field_validator("request_fingerprint", "result_fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return _fingerprint(value, field=info.field_name)

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _utc(value)


class HumanApprovalEvidence(_EngineeringMemoryContract):
    approval_id: str
    record_id: str
    record_revision: int = Field(ge=0)
    approved_by: str
    reason_code: Literal["PROJECT_ACCEPTED", "RISK_ACCEPTED", "WORKAROUND_ACCEPTED"]
    approved_at: datetime

    @field_validator("approval_id", "record_id", "approved_by", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("approved_at")
    @classmethod
    def validate_approved_at(cls, value: datetime) -> datetime:
        return _utc(value)


class EngineeringMemoryRecord(_EngineeringMemoryContract):
    project_id: str
    memory_id: str
    record_id: str
    memory_type: MemoryType
    logical_key: str
    payload: MemoryPayload
    provenance: MemoryProvenance
    status: MemoryStatus
    record_revision: int = Field(ge=0)
    created_aggregate_revision: int = Field(ge=1)
    last_updated_aggregate_revision: int = Field(ge=1)
    created_at: datetime
    last_transition_at: datetime
    verification_bindings: tuple[VerificationEvidenceBinding, ...] = ()
    approval_binding: HumanApprovalEvidence | None = None
    state_history: tuple[MemoryStateTransition, ...] = Field(min_length=1)
    supersedes_record_id: str | None = None
    superseded_by_record_id: str | None = None

    @field_validator("project_id", "memory_id", "record_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("logical_key", mode="before")
    @classmethod
    def validate_logical_key(cls, value: object) -> str:
        return _safe_derived_reference(value, field="logical_key")

    @field_validator("supersedes_record_id", "superseded_by_record_id", mode="before")
    @classmethod
    def validate_optional_identifiers(cls, value: object, info) -> object:
        if value is None:
            return value
        return _identifier(value, field=info.field_name)

    @field_validator("created_at", "last_transition_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_record_consistency(self) -> EngineeringMemoryRecord:
        if self.payload.memory_type is not self.memory_type:
            raise ValueError("record memory type is invalid")
        if self.created_aggregate_revision > self.last_updated_aggregate_revision:
            raise ValueError("record aggregate revisions are invalid")
        if self.record_revision != len(self.state_history) - 1:
            raise ValueError("record revision does not match state history")
        first = self.state_history[0]
        if (
            first.from_status is not None
            or first.to_status is not MemoryStatus.CANDIDATE
        ):
            raise ValueError("initial state transition is invalid")
        if self.state_history[-1].to_status is not self.status:
            raise ValueError("record status does not match state history")
        if self.last_transition_at != self.state_history[-1].transitioned_at:
            raise ValueError("last transition timestamp is invalid")
        return self


_PAYLOAD_TYPES = (
    BoardProfileMemory,
    ComponentMemory,
    PinBindingMemory,
    InterfaceBindingMemory,
    PowerConstraintMemory,
    EngineeringDecisionMemory,
    KnownIssueMemory,
    VerificationHistoryMemory,
)


def _typed_payload(value: object) -> object:
    if not isinstance(value, _PAYLOAD_TYPES):
        raise ValueError(  # noqa: TRY004
            "payload must be a typed memory contract"
        )
    return value


class CreateCandidateRequest(_MemoryWriteRequestContract):
    command_type: Literal[MemoryCommandType.CREATE_CANDIDATE] = (
        MemoryCommandType.CREATE_CANDIDATE
    )
    record_id: str
    payload: MemoryPayload
    provenance: MemoryProvenance

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")

    @field_validator("payload", mode="before")
    @classmethod
    def validate_payload(cls, value: object) -> object:
        return _typed_payload(value)

    @field_validator("provenance", mode="before")
    @classmethod
    def validate_provenance(cls, value: object) -> object:
        if not isinstance(value, MemoryProvenance):
            raise ValueError(  # noqa: TRY004
                "provenance must be a typed memory contract"
            )
        return value


class CreateReplacementCandidateRequest(CreateCandidateRequest):
    command_type: Literal[MemoryCommandType.CREATE_REPLACEMENT_CANDIDATE] = (
        MemoryCommandType.CREATE_REPLACEMENT_CANDIDATE
    )
    supersedes_record_id: str

    @field_validator("supersedes_record_id", mode="before")
    @classmethod
    def validate_supersedes_record_id(cls, value: object) -> str:
        return _identifier(value, field="supersedes_record_id")


class ApplyVerificationRequest(_MemoryWriteRequestContract):
    command_type: Literal[MemoryCommandType.APPLY_VERIFICATION] = (
        MemoryCommandType.APPLY_VERIFICATION
    )
    record_id: str
    record_revision: int = Field(ge=0)
    verification_request: VerificationRequest
    verification_result: VerificationResult

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")

    @model_validator(mode="after")
    def validate_verification_ids(self) -> ApplyVerificationRequest:
        if self.verification_request.request_id != self.verification_result.request_id:
            raise ValueError("verification request and result do not match")
        return self


class ApplyHumanApprovalRequest(_MemoryWriteRequestContract):
    command_type: Literal[MemoryCommandType.APPLY_HUMAN_APPROVAL] = (
        MemoryCommandType.APPLY_HUMAN_APPROVAL
    )
    record_id: str
    record_revision: int = Field(ge=0)
    approval: HumanApprovalEvidence

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")

    @model_validator(mode="after")
    def validate_approval_binding(self) -> ApplyHumanApprovalRequest:
        if (
            self.approval.record_id != self.record_id
            or self.approval.record_revision != self.record_revision
        ):
            raise ValueError("approval does not match record")
        return self


class RevokeRecordRequest(_MemoryWriteRequestContract):
    command_type: Literal[MemoryCommandType.REVOKE_RECORD] = (
        MemoryCommandType.REVOKE_RECORD
    )
    record_id: str
    record_revision: int = Field(ge=0)
    reason_code: Literal["NO_LONGER_VALID", "PROJECT_CANCELLED", "SOURCE_RETRACTED"]

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")


class GetVerifiedSnapshotRequest(_MemoryRequestContract):
    command_type: Literal[MemoryCommandType.GET_VERIFIED_SNAPSHOT] = (
        MemoryCommandType.GET_VERIFIED_SNAPSHOT
    )


class GetCandidateSnapshotRequest(_MemoryRequestContract):
    command_type: Literal[MemoryCommandType.GET_CANDIDATE_SNAPSHOT] = (
        MemoryCommandType.GET_CANDIDATE_SNAPSHOT
    )


class GetHistoryRequest(_MemoryRequestContract):
    command_type: Literal[MemoryCommandType.GET_HISTORY] = MemoryCommandType.GET_HISTORY
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)

    @field_validator("cursor", mode="before")
    @classmethod
    def validate_cursor(cls, value: object) -> object:
        if value is None:
            return value
        if not isinstance(value, str) or not _CURSOR.fullmatch(value):
            raise ValueError("history cursor is invalid")
        return value


EngineeringMemoryRequest: TypeAlias = Annotated[
    CreateCandidateRequest
    | CreateReplacementCandidateRequest
    | ApplyVerificationRequest
    | ApplyHumanApprovalRequest
    | RevokeRecordRequest
    | GetVerifiedSnapshotRequest
    | GetCandidateSnapshotRequest
    | GetHistoryRequest,
    Field(discriminator="command_type"),
]


class MemoryAuthorizationRequest(_EngineeringMemoryContract):
    request_id: str
    operation_id: str | None
    project_id: str
    memory_id: str
    caller: str
    command_type: MemoryCommandType
    action: MemoryAction
    request_fingerprint: str
    requested_at: datetime

    @field_validator("request_id", "project_id", "memory_id", "caller", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("operation_id", mode="before")
    @classmethod
    def validate_operation_id(cls, value: object) -> object:
        if value is None:
            return value
        return _identifier(value, field="operation_id")

    @field_validator("request_fingerprint", mode="before")
    @classmethod
    def validate_request_fingerprint(cls, value: object) -> str:
        return _fingerprint(value, field="request_fingerprint")

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _utc(value)


class MemoryPermissionDecision(MemoryAuthorizationRequest):
    decision: MemoryPermissionStatus
    reason_code: Literal["AUTHORIZED", "POLICY_DENIED"]

    @model_validator(mode="after")
    def validate_decision_reason(self) -> MemoryPermissionDecision:
        if (
            self.decision is MemoryPermissionStatus.ALLOWED
            and self.reason_code != "AUTHORIZED"
        ) or (
            self.decision is MemoryPermissionStatus.DENIED
            and self.reason_code == "AUTHORIZED"
        ):
            raise ValueError("permission reason is invalid")
        return self


class MemoryAuditEvent(_EngineeringMemoryContract):
    event_key: str
    event_type: MemoryAuditEventType
    request_id: str
    operation_id: str | None
    project_id: str
    memory_id: str
    record_id: str | None
    command_type: MemoryCommandType
    timestamp: datetime

    @field_validator("event_key", mode="before")
    @classmethod
    def validate_event_key(cls, value: object) -> str:
        return _safe_reference(value, field="event_key")

    @field_validator("request_id", "project_id", "memory_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("operation_id", "record_id", mode="before")
    @classmethod
    def validate_optional_identifiers(cls, value: object, info) -> object:
        if value is None:
            return value
        return _identifier(value, field=info.field_name)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)


class AffectedMemoryRecord(_EngineeringMemoryContract):
    record_id: str
    status: MemoryStatus
    record_revision: int = Field(ge=0)

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")


class MemoryMutationResult(_EngineeringMemoryContract):
    request_id: str
    operation_id: str
    command_type: MemoryCommandType
    outcome: MemoryMutationOutcome
    affected_records: tuple[AffectedMemoryRecord, ...] = Field(min_length=1)
    aggregate_revision: int = Field(ge=1)

    @field_validator("request_id", "operation_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_affected_records(self) -> MemoryMutationResult:
        ids = tuple(item.record_id for item in self.affected_records)
        if len(ids) != len(set(ids)):
            raise ValueError("affected records must be unique")
        return self


class MemorySnapshotRecord(_EngineeringMemoryContract):
    record_id: str
    memory_type: MemoryType
    logical_key: str
    payload: MemoryPayload
    provenance: MemoryProvenance
    status: MemoryStatus
    record_revision: int = Field(ge=0)
    supersedes_record_id: str | None = None


class EngineeringMemorySnapshot(_EngineeringMemoryContract):
    request_id: str
    snapshot_type: MemorySnapshotType
    project_id: str
    memory_id: str
    aggregate_revision: int = Field(ge=0)
    board_profile: MemorySnapshotRecord | None = None
    components: tuple[MemorySnapshotRecord, ...] = ()
    pin_bindings: tuple[MemorySnapshotRecord, ...] = ()
    interface_bindings: tuple[MemorySnapshotRecord, ...] = ()
    power_constraints: tuple[MemorySnapshotRecord, ...] = ()
    engineering_decisions: tuple[MemorySnapshotRecord, ...] = ()
    known_issues: tuple[MemorySnapshotRecord, ...] = ()
    verification_records: tuple[MemorySnapshotRecord, ...] = ()
    snapshot_fingerprint: str

    @field_validator("request_id", "project_id", "memory_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("snapshot_fingerprint", mode="before")
    @classmethod
    def validate_snapshot_fingerprint(cls, value: object) -> str:
        return _fingerprint(value, field="snapshot_fingerprint")

    @property
    def records(self) -> tuple[MemorySnapshotRecord, ...]:
        board = () if self.board_profile is None else (self.board_profile,)
        return (
            board
            + self.components
            + self.pin_bindings
            + self.interface_bindings
            + self.power_constraints
            + self.engineering_decisions
            + self.known_issues
            + self.verification_records
        )


class EngineeringMemoryHistoryPage(_EngineeringMemoryContract):
    request_id: str
    project_id: str
    memory_id: str
    aggregate_revision: int = Field(ge=0)
    records: tuple[EngineeringMemoryRecord, ...]
    next_cursor: str | None = None
    has_more: bool

    @field_validator("request_id", "project_id", "memory_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("next_cursor", mode="before")
    @classmethod
    def validate_next_cursor(cls, value: object) -> object:
        return GetHistoryRequest.validate_cursor(value)

    @model_validator(mode="after")
    def validate_pagination(self) -> EngineeringMemoryHistoryPage:
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("history pagination is invalid")
        return self


EngineeringMemoryResult: TypeAlias = (
    MemoryMutationResult | EngineeringMemorySnapshot | EngineeringMemoryHistoryPage
)
