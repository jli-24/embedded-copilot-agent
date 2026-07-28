from __future__ import annotations

import copy
import math
import re
import unicodedata
from collections.abc import Sequence
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.coding_runtime import FrozenCodeContextSnapshot
from embedded_copilot.context_runtime.contracts import EngineeringContextResponse

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_CONTEXT_ID = re.compile(r"^context:[a-f0-9]{24}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_REGISTER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
_HEX_VALUE = re.compile(r"^0x[0-9a-f]{1,16}$")
_FUNCTION = re.compile(r"^[A-Za-z_][A-Za-z0-9_:.<>~-]{0,159}$")
_METRIC = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
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
_DEVICE_SECRET = re.compile(
    r"(?:serial(?:[ _-]?number)?|unique(?:[ _-]?id)?|\buid\b)",
    re.IGNORECASE,
)
_MEMORY_CONTENT = re.compile(
    r"\b(?:memory|ram|flash)\s+(?:dump|content)\b",
    re.IGNORECASE,
)


class _DebugContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )


class DebugSourceType(StrEnum):
    UART = "UART"
    JLINK = "JLINK"
    STLINK = "STLINK"
    GDB = "GDB"


class DebugSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    DEBUG = "DEBUG"
    INFO = "INFO"


class TelemetryUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    BYTES = "bytes"
    MILLISECONDS = "milliseconds"
    CELSIUS = "celsius"
    VOLTS = "volts"
    AMPERES = "amperes"
    HERTZ = "hertz"


class DebugAuditEventType(StrEnum):
    TARGET_IDENTIFIED = "TARGET_IDENTIFIED"
    TARGET_IDENTIFICATION_FAILED = "TARGET_IDENTIFICATION_FAILED"
    SNAPSHOT_COLLECTED = "SNAPSHOT_COLLECTED"
    SNAPSHOT_COLLECTION_FAILED = "SNAPSHOT_COLLECTION_FAILED"
    TELEMETRY_COLLECTED = "TELEMETRY_COLLECTED"
    TELEMETRY_COLLECTION_FAILED = "TELEMETRY_COLLECTION_FAILED"


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not _IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(timezone.utc)


def _safe_text(
    value: object,
    *,
    field: str,
    max_length: int,
    reject_device_secret: bool = False,
    reject_memory_content: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > max_length
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE_TEXT.search(candidate)
        or (reject_device_secret and _DEVICE_SECRET.search(candidate))
        or (reject_memory_content and _MEMORY_CONTENT.search(candidate))
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


class TargetIdentificationRequest(_DebugContract):
    target_id: str
    source_type: DebugSourceType
    observed_at: datetime

    @field_validator("target_id", mode="before")
    @classmethod
    def validate_target_id(cls, value: object) -> str:
        return _identifier(value, field="target_id")

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _utc(value)


class DebugSnapshotRequest(TargetIdentificationRequest):
    snapshot_id: str

    @field_validator("snapshot_id", mode="before")
    @classmethod
    def validate_snapshot_id(cls, value: object) -> str:
        return _identifier(value, field="snapshot_id")


class TelemetryRequest(TargetIdentificationRequest):
    pass


class TargetIdentity(_DebugContract):
    vendor: str
    family: str
    architecture: str
    device: str
    core: str

    @field_validator(
        "vendor", "family", "architecture", "device", "core", mode="before"
    )
    @classmethod
    def validate_identity(cls, value: object, info) -> str:
        return _safe_text(
            value,
            field=info.field_name,
            max_length=64,
            reject_device_secret=True,
        )


class UARTLogRecord(_DebugContract):
    sequence: int = Field(ge=0)
    timestamp: datetime
    log_line: str

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("log_line", mode="before")
    @classmethod
    def validate_log_line(cls, value: object) -> str:
        return _safe_text(
            value,
            field="log_line",
            max_length=512,
            reject_memory_content=True,
        )


class RegisterRecord(_DebugContract):
    register_name: str = Field(alias="register")
    value: str

    @field_validator("register_name", mode="before")
    @classmethod
    def validate_register(cls, value: object) -> str:
        if not isinstance(value, str) or not _REGISTER.fullmatch(value.strip()):
            raise ValueError("register is invalid")
        return value.strip().upper()

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("register value is invalid")
        candidate = value.strip().casefold()
        if not _HEX_VALUE.fullmatch(candidate):
            raise ValueError("register value is invalid")
        return candidate

    @property
    def register(self) -> str:
        return self.register_name


class StackFrameRecord(_DebugContract):
    frame_index: int = Field(ge=0, le=63)
    function: str
    address: str

    @field_validator("function", mode="before")
    @classmethod
    def validate_function(cls, value: object) -> str:
        if not isinstance(value, str) or not _FUNCTION.fullmatch(value.strip()):
            raise ValueError("stack function is invalid")
        return value.strip()

    @field_validator("address", mode="before")
    @classmethod
    def validate_address(cls, value: object) -> str:
        return RegisterRecord.validate_value(value)


class TelemetryMetric(_DebugContract):
    name: str
    value: int | float
    unit: TelemetryUnit

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        if not isinstance(value, str) or not _METRIC.fullmatch(value.strip()):
            raise ValueError("metric name is invalid")
        return value.strip()

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> int | float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("metric value is invalid")
        return copy.deepcopy(value)


class DebugSourceCapture(_DebugContract):
    source_type: DebugSourceType
    target_identity: TargetIdentity
    observations: tuple[UARTLogRecord | RegisterRecord | StackFrameRecord, ...] = Field(
        max_length=384
    )
    telemetry: tuple[TelemetryMetric, ...] = Field(max_length=64)


class UARTObservation(_DebugContract):
    kind: Literal["UART"] = "UART"
    sequence: int = Field(ge=0)
    timestamp: datetime
    severity: DebugSeverity
    log_line: str

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("log_line", mode="before")
    @classmethod
    def validate_log_line(cls, value: object) -> str:
        return UARTLogRecord.validate_log_line(value)


class RegisterObservation(_DebugContract):
    kind: Literal["REGISTER"] = "REGISTER"
    register_name: str = Field(alias="register")
    value: str

    @field_validator("register_name", mode="before")
    @classmethod
    def validate_register(cls, value: object) -> str:
        return RegisterRecord.validate_register(value)

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> str:
        return RegisterRecord.validate_value(value)

    @property
    def register(self) -> str:
        return self.register_name


class StackFrameObservation(_DebugContract):
    kind: Literal["STACK_FRAME"] = "STACK_FRAME"
    frame_index: int = Field(ge=0, le=63)
    function: str
    address: str

    @field_validator("function", mode="before")
    @classmethod
    def validate_function(cls, value: object) -> str:
        return StackFrameRecord.validate_function(value)

    @field_validator("address", mode="before")
    @classmethod
    def validate_address(cls, value: object) -> str:
        return StackFrameRecord.validate_address(value)


class TelemetrySnapshot(_DebugContract):
    schema_version: Literal["1.0"] = "1.0"
    target_id: str
    source_type: DebugSourceType
    captured_at: datetime
    metrics: tuple[TelemetryMetric, ...] = Field(max_length=64)

    @field_validator("target_id", mode="before")
    @classmethod
    def validate_target_id(cls, value: object) -> str:
        return _identifier(value, field="target_id")

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_metrics(self) -> "TelemetrySnapshot":
        names = tuple(item.name.casefold() for item in self.metrics)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("telemetry metrics must be sorted and unique")
        return self


class FrozenDebugSnapshot(_DebugContract):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_id: str
    target_identity: TargetIdentity
    observations: tuple[
        UARTObservation | RegisterObservation | StackFrameObservation, ...
    ] = Field(max_length=384)
    telemetry: TelemetrySnapshot
    source_type: DebugSourceType
    fingerprint: str

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
            raise ValueError("fingerprint is invalid")
        return value.strip()

    @field_validator("snapshot_id", mode="before")
    @classmethod
    def validate_snapshot_id(cls, value: object) -> str:
        return _identifier(value, field="snapshot_id")

    @model_validator(mode="after")
    def validate_snapshot(self) -> "FrozenDebugSnapshot":
        if self.telemetry.source_type is not self.source_type:
            raise ValueError("snapshot telemetry source does not match")
        from embedded_copilot.debug_runtime.snapshot import snapshot_fingerprint

        expected = snapshot_fingerprint(
            schema_version=self.schema_version,
            snapshot_id=self.snapshot_id,
            target_identity=self.target_identity,
            observations=self.observations,
            telemetry=self.telemetry,
            source_type=self.source_type,
        )
        if self.fingerprint != expected:
            raise ValueError("fingerprint does not match snapshot")
        return self


class DebugAuditEvent(_DebugContract):
    event_type: DebugAuditEventType
    target_id: str
    source_type: DebugSourceType
    timestamp: datetime

    @field_validator("target_id", mode="before")
    @classmethod
    def validate_target_id(cls, value: object) -> str:
        return _identifier(value, field="target_id")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)


class DebugReasoningContext(_DebugContract):
    context_id: str
    debug_snapshot: FrozenDebugSnapshot
    code_snapshot: FrozenCodeContextSnapshot | None = None
    engineering_context: EngineeringContextResponse | None = None

    @field_validator("context_id", mode="before")
    @classmethod
    def validate_context_id(cls, value: object) -> str:
        if not isinstance(value, str) or not _CONTEXT_ID.fullmatch(value.strip()):
            raise ValueError("context_id is invalid")
        return value.strip()

    @model_validator(mode="after")
    def validate_context_binding(self) -> "DebugReasoningContext":
        if (
            self.code_snapshot is not None
            and self.code_snapshot.context_id != self.context_id
        ):
            raise ValueError("code snapshot context does not match")
        if (
            self.engineering_context is not None
            and self.engineering_context.context_summary.context_id != self.context_id
        ):
            raise ValueError("engineering context does not match")
        return self


def _safe_text_tuple(
    value: object,
    *,
    field: str,
    max_items: int,
) -> object:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return value
    copied = copy.deepcopy(value)
    items = tuple(_safe_text(item, field=field, max_length=512) for item in copied)
    if len(items) > max_items or len(set(items)) != len(items):
        raise ValueError(f"{field} is invalid")
    return items


class DebugInsight(_DebugContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    evidence: tuple[str, ...] = Field(max_length=32)
    possible_causes: tuple[str, ...] = Field(max_length=16)
    suggested_checks: tuple[str, ...] = Field(max_length=16)
    review_required: Literal[True] = True

    @field_validator("evidence", "possible_causes", "suggested_checks", mode="before")
    @classmethod
    def validate_text_collections(cls, value: object, info) -> object:
        limits = {"evidence": 32, "possible_causes": 16, "suggested_checks": 16}
        return _safe_text_tuple(
            value,
            field=info.field_name,
            max_items=limits[info.field_name],
        )
