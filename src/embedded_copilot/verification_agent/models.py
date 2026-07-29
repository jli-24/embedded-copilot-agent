from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.coding_runtime import (
    FrozenCodeContextSnapshot,
    HardwareSoftwareFusionRequest,
)
from embedded_copilot.tool_runtime import FirmwareBuildOutput, ToolResult

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_PIN = re.compile(r"^(?:P[A-Z][0-9]{1,2}|GPIO[0-9]{1,2})$")
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?<![A-Za-z0-9._~-])/[^/\s]+)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+|"
    r"(?:password|credential|secret)\s*[:=]|(?:^|\s)sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


class _VerificationContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


class VerificationSubjectType(StrEnum):
    FIRMWARE = "FIRMWARE"
    HARDWARE = "HARDWARE"
    TOOL_RESULT = "TOOL_RESULT"


class VerificationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class VerificationSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class VerificationFindingCategory(StrEnum):
    BUILD_STATUS = "BUILD_STATUS"
    BUILD_WARNING = "BUILD_WARNING"
    RESOURCE_USAGE = "RESOURCE_USAGE"
    PIN_CONFLICT = "PIN_CONFLICT"
    INTERFACE_CONFLICT = "INTERFACE_CONFLICT"
    POWER_CONSTRAINT = "POWER_CONSTRAINT"
    TOOL_STATUS = "TOOL_STATUS"
    TOOL_OUTPUT = "TOOL_OUTPUT"
    TOOL_TRUST = "TOOL_TRUST"
    TOOL_METRIC = "TOOL_METRIC"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class VerificationAuditEventType(StrEnum):
    VERIFICATION_REQUESTED = "VERIFICATION_REQUESTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not _IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _name(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not _NAME.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _safe_text(value: object, *, field: str, max_length: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
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


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(timezone.utc)


class FirmwareResourceUsage(_VerificationContract):
    resource_name: str
    used_bytes: int = Field(ge=0)
    limit_bytes: int = Field(gt=0)

    @field_validator("resource_name", mode="before")
    @classmethod
    def validate_resource_name(cls, value: object) -> str:
        return _name(value, field="resource_name")


class FirmwareVerificationSubject(_VerificationContract):
    build_output: FirmwareBuildOutput
    code_context: FrozenCodeContextSnapshot | None = None
    resources: tuple[FirmwareResourceUsage, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def validate_resources(self) -> "FirmwareVerificationSubject":
        names = tuple(item.resource_name for item in self.resources)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("resources must be sorted and unique")
        return self


class InterfaceBindingCandidate(_VerificationContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    reference_id: str
    interface_id: str
    signal: str
    pin: str

    @field_validator("reference_id", mode="before")
    @classmethod
    def validate_reference_id(cls, value: object) -> str:
        return _identifier(value, field="reference_id")

    @field_validator("interface_id", mode="before")
    @classmethod
    def validate_interface_id(cls, value: object) -> str:
        return _name(value, field="interface_id")

    @field_validator("signal", mode="before")
    @classmethod
    def validate_signal(cls, value: object) -> str:
        return _identifier(value, field="signal")

    @field_validator("pin", mode="before")
    @classmethod
    def validate_pin(cls, value: object) -> str:
        if not isinstance(value, str) or not _PIN.fullmatch(value.strip().upper()):
            raise ValueError("pin is invalid")
        return value.strip().upper()


class PowerConnectionCandidate(_VerificationContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    source_reference_id: str
    load_reference_id: str
    supply_min_v: float
    supply_max_v: float
    required_min_v: float
    required_max_v: float

    @field_validator("source_reference_id", "load_reference_id", mode="before")
    @classmethod
    def validate_reference_ids(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator(
        "supply_min_v",
        "supply_max_v",
        "required_min_v",
        "required_max_v",
    )
    @classmethod
    def validate_voltage(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("voltage is invalid")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> "PowerConnectionCandidate":
        if self.supply_min_v > self.supply_max_v:
            raise ValueError("supply voltage range is reversed")
        if self.required_min_v > self.required_max_v:
            raise ValueError("required voltage range is reversed")
        return self


class HardwareVerificationSubject(_VerificationContract):
    fusion_request: HardwareSoftwareFusionRequest
    interface_bindings: tuple[InterfaceBindingCandidate, ...] = Field(
        default=(), max_length=128
    )
    power_connections: tuple[PowerConnectionCandidate, ...] = Field(
        default=(), max_length=64
    )

    @model_validator(mode="after")
    def validate_bindings(self) -> "HardwareVerificationSubject":
        reference_ids = {
            item.file_id
            for item in self.fusion_request.engineering_context.context_summary.datasheets
        }
        pin_candidates = {
            (item.reference_id, item.pin, item.function)
            for item in self.fusion_request.pin_candidates
        }
        binding_keys = tuple(
            (item.reference_id, item.interface_id, item.signal, item.pin)
            for item in self.interface_bindings
        )
        if binding_keys != tuple(sorted(binding_keys)) or len(binding_keys) != len(
            set(binding_keys)
        ):
            raise ValueError("interface bindings must be sorted and unique")
        if any(
            item.reference_id not in reference_ids
            or (item.reference_id, item.pin, item.signal) not in pin_candidates
            for item in self.interface_bindings
        ):
            raise ValueError("interface binding is not bound to a pin candidate")
        power_keys = tuple(
            (
                item.source_reference_id,
                item.load_reference_id,
                item.supply_min_v,
                item.supply_max_v,
                item.required_min_v,
                item.required_max_v,
            )
            for item in self.power_connections
        )
        if power_keys != tuple(sorted(power_keys)) or len(power_keys) != len(
            set(power_keys)
        ):
            raise ValueError("power connections must be sorted and unique")
        if any(
            item.source_reference_id not in reference_ids
            or item.load_reference_id not in reference_ids
            for item in self.power_connections
        ):
            raise ValueError("power connection is not bound to datasheet candidates")
        return self


class ToolResultVerificationSubject(_VerificationContract):
    result: ToolResult


VerificationSubject: TypeAlias = (
    FirmwareVerificationSubject
    | HardwareVerificationSubject
    | ToolResultVerificationSubject
)


class VerificationFinding(_VerificationContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    severity: VerificationSeverity
    category: VerificationFindingCategory
    message: str
    evidence: tuple[str, ...] = Field(min_length=1, max_length=16)
    recommendation: str

    @field_validator("message", "recommendation", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence(cls, value: object) -> object:
        if not isinstance(value, (tuple, list)):
            return value
        evidence = tuple(_safe_text(item, field="evidence") for item in value)
        if len(evidence) != len(set(evidence)):
            raise ValueError("evidence must be unique")
        return evidence


class VerificationCheckResult(_VerificationContract):
    status: VerificationStatus
    findings: tuple[VerificationFinding, ...] = Field(default=(), max_length=128)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("confidence is invalid")
        return value

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="summary")

    @model_validator(mode="after")
    def validate_status(self) -> "VerificationCheckResult":
        if self.status is VerificationStatus.PASS and self.findings:
            raise ValueError("PASS result must not contain findings")
        if self.status is not VerificationStatus.PASS and not self.findings:
            raise ValueError("non-PASS result requires findings")
        return self


class VerificationResult(VerificationCheckResult):
    request_id: str

    @field_validator("request_id", mode="before")
    @classmethod
    def validate_request_id(cls, value: object) -> str:
        return _identifier(value, field="request_id")


class VerificationRequest(_VerificationContract):
    request_id: str
    subject_type: VerificationSubjectType
    subject: VerificationSubject
    context_id: str
    requested_at: datetime

    @field_validator("request_id", "context_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_subject_binding(self) -> "VerificationRequest":
        expected = {
            VerificationSubjectType.FIRMWARE: FirmwareVerificationSubject,
            VerificationSubjectType.HARDWARE: HardwareVerificationSubject,
            VerificationSubjectType.TOOL_RESULT: ToolResultVerificationSubject,
        }[self.subject_type]
        if not isinstance(self.subject, expected):
            raise ValueError("subject type does not match subject")
        if (
            isinstance(self.subject, FirmwareVerificationSubject)
            and self.subject.code_context is not None
            and self.subject.code_context.context_id != self.context_id
        ):
            raise ValueError("firmware context does not match request")
        if (
            isinstance(self.subject, HardwareVerificationSubject)
            and self.subject.fusion_request.snapshot.context_id != self.context_id
        ):
            raise ValueError("hardware context does not match request")
        return self


class VerificationAuditEvent(_VerificationContract):
    event_type: VerificationAuditEventType
    request_id: str
    subject_type: VerificationSubjectType
    timestamp: datetime

    @field_validator("request_id", mode="before")
    @classmethod
    def validate_request_id(cls, value: object) -> str:
        return _identifier(value, field="request_id")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)


def checker_name(value: object) -> str:
    return _name(value, field="checker_name")
