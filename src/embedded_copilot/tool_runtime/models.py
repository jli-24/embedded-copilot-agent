from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_METRIC_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?<![A-Za-z0-9._~-])/"
    r"(?:[^/\s]+(?:/[^/\s]+)*))",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|(?:password|credential|secret)\s*[:=]"
    r"|(?:^|\s)sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


class _ToolContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


class ToolBuildSystem(StrEnum):
    ESP_IDF = "ESP_IDF"
    CMAKE = "CMAKE"
    MAKE = "MAKE"


class ToolCompiler(StrEnum):
    GCC = "GCC"
    CLANG = "CLANG"
    ARM_NONE_EABI_GCC = "ARM_NONE_EABI_GCC"


class BuildStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class SerialSourceType(StrEnum):
    UART = "UART"


class SerialSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    DEBUG = "DEBUG"
    INFO = "INFO"


class ToolResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class ToolMetricUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    BYTES = "bytes"
    MILLISECONDS = "milliseconds"


class ToolPermissionStatus(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class ToolPermissionReason(StrEnum):
    AUTHORIZED = "authorized"
    CALLER_DENIED = "caller_denied"
    TOOL_DENIED = "tool_denied"
    CAPABILITY_DENIED = "capability_denied"


class ToolAuditEventType(StrEnum):
    TOOL_REQUESTED = "TOOL_REQUESTED"
    TOOL_SUCCEEDED = "TOOL_SUCCEEDED"
    TOOL_FAILED = "TOOL_FAILED"
    TOOL_REJECTED = "TOOL_REJECTED"


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not _IDENTIFIER.fullmatch(candidate)
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE_TEXT.search(candidate)
        or "/" in candidate
        or "\\" in candidate
    ):
        raise ValueError(f"{field} is invalid")
    return candidate


def _tool_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("tool_name is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not _TOOL_NAME.fullmatch(candidate):
        raise ValueError("tool_name is invalid")
    return candidate


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(timezone.utc)


def _safe_text(value: object, *, field: str, max_length: int = 256) -> str:
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


def _finite_number(value: object) -> int | float:
    if isinstance(value, bool):
        raise ValueError("numeric value is invalid")
    if isinstance(value, int):
        try:
            if math.isfinite(value):
                return value
        except OverflowError:
            pass
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("numeric value is invalid")


class CompileFirmwareArguments(_ToolContract):
    project_id: str
    build_system: ToolBuildSystem
    workspace_reference: str

    @field_validator("project_id", "workspace_reference", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


class ReadSerialLogArguments(_ToolContract):
    target_id: str
    source_type: SerialSourceType

    @field_validator("target_id", mode="before")
    @classmethod
    def validate_target_id(cls, value: object) -> str:
        return _identifier(value, field="target_id")


class RunFirmwareTestArguments(_ToolContract):
    project_id: str
    test_id: str
    workspace_reference: str

    @field_validator(
        "project_id",
        "test_id",
        "workspace_reference",
        mode="before",
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


ToolArguments: TypeAlias = (
    CompileFirmwareArguments | ReadSerialLogArguments | RunFirmwareTestArguments
)


class ToolRequest(_ToolContract):
    request_id: str
    tool_name: str
    arguments: ToolArguments
    caller: str

    @field_validator("request_id", "caller", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("tool_name", mode="before")
    @classmethod
    def validate_tool_name(cls, value: object) -> str:
        return _tool_name(value)


class ToolExecutionContext(_ToolContract):
    request: ToolRequest
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _utc(value)


def tool_request_fingerprint(request: ToolRequest) -> str:
    validated = ToolRequest.model_validate(
        copy.deepcopy(request.model_dump(mode="python"))
    )
    payload = validated.model_dump(mode="json")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class ToolPermissionDecision(_ToolContract):
    request_id: str
    tool_name: str
    caller: str
    request_fingerprint: str
    decision: ToolPermissionStatus
    reason_code: ToolPermissionReason

    @field_validator("request_id", "caller", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("tool_name", mode="before")
    @classmethod
    def validate_tool_name(cls, value: object) -> str:
        return _tool_name(value)

    @field_validator("request_fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
            raise ValueError("request_fingerprint is invalid")
        return value.strip()

    @model_validator(mode="after")
    def validate_reason(self) -> "ToolPermissionDecision":
        if (
            self.decision is ToolPermissionStatus.ALLOWED
            and self.reason_code is not ToolPermissionReason.AUTHORIZED
        ):
            raise ValueError("allowed permission reason is invalid")
        if (
            self.decision is ToolPermissionStatus.DENIED
            and self.reason_code is ToolPermissionReason.AUTHORIZED
        ):
            raise ValueError("denied permission reason is invalid")
        return self


class FirmwareBuildOutput(_ToolContract):
    execution_mode: Literal["MOCK"] = "MOCK"
    build_status: BuildStatus
    compiler: ToolCompiler
    warnings_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    summary: str

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="summary")


class FirmwareTestOutput(_ToolContract):
    execution_mode: Literal["MOCK"] = "MOCK"
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    duration_ms: int | float = Field(ge=0)
    summary: str

    @field_validator("duration_ms", mode="before")
    @classmethod
    def validate_duration(cls, value: object) -> int | float:
        candidate = _finite_number(value)
        if candidate < 0:
            raise ValueError("duration_ms is invalid")
        return candidate

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="summary")


class SerialLogLine(_ToolContract):
    sequence: int = Field(ge=0)
    timestamp: datetime
    severity: SerialSeverity
    log_line: str

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("log_line", mode="before")
    @classmethod
    def validate_log_line(cls, value: object) -> str:
        return _safe_text(value, field="log_line", max_length=512)


class SerialSeverityCount(_ToolContract):
    severity: SerialSeverity
    count: int = Field(ge=0, le=256)


class SerialLogOutput(_ToolContract):
    lines: tuple[SerialLogLine, ...] = Field(max_length=256)
    severity_summary: tuple[SerialSeverityCount, ...] = Field(
        min_length=5,
        max_length=5,
    )

    @model_validator(mode="after")
    def validate_ordering(self) -> "SerialLogOutput":
        ordering = tuple((item.sequence, item.timestamp) for item in self.lines)
        if ordering != tuple(sorted(ordering)) or len(ordering) != len(set(ordering)):
            raise ValueError("serial lines must be sorted and unique")
        expected = tuple(SerialSeverity)
        actual = tuple(item.severity for item in self.severity_summary)
        if actual != expected:
            raise ValueError("severity summary order is invalid")
        return self


ToolOutput: TypeAlias = FirmwareBuildOutput | SerialLogOutput | FirmwareTestOutput


class ToolArtifactReference(_ToolContract):
    reference_id: str
    artifact_type: str
    status: str

    @field_validator("reference_id", "artifact_type", "status", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


class ToolMetric(_ToolContract):
    name: str
    value: int | float
    unit: ToolMetricUnit

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        if not isinstance(value, str) or not _METRIC_NAME.fullmatch(value.strip()):
            raise ValueError("metric name is invalid")
        return value.strip()

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> int | float:
        return _finite_number(value)


def _validate_collections(
    artifacts: tuple[ToolArtifactReference, ...],
    metrics: tuple[ToolMetric, ...],
) -> None:
    artifact_ids = tuple(item.reference_id for item in artifacts)
    metric_names = tuple(item.name for item in metrics)
    if artifact_ids != tuple(sorted(artifact_ids)) or len(artifact_ids) != len(
        set(artifact_ids)
    ):
        raise ValueError("artifacts must be sorted and unique")
    if metric_names != tuple(sorted(metric_names)) or len(metric_names) != len(
        set(metric_names)
    ):
        raise ValueError("metrics must be sorted and unique")


class ToolAdapterResult(_ToolContract):
    status: ToolResultStatus
    summary: str
    output: ToolOutput | None = None
    artifacts: tuple[ToolArtifactReference, ...] = Field(default=(), max_length=64)
    metrics: tuple[ToolMetric, ...] = Field(default=(), max_length=64)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="summary")

    @model_validator(mode="after")
    def validate_result(self) -> "ToolAdapterResult":
        if self.status is not ToolResultStatus.SUCCESS and self.output is not None:
            raise ValueError("non-success adapter result must not contain output")
        _validate_collections(self.artifacts, self.metrics)
        return self


class ToolResult(_ToolContract):
    request_id: str
    tool_name: str
    status: ToolResultStatus
    summary: str
    output: ToolOutput | None = None
    artifacts: tuple[ToolArtifactReference, ...] = Field(default=(), max_length=64)
    metrics: tuple[ToolMetric, ...] = Field(default=(), max_length=64)

    @field_validator("request_id", mode="before")
    @classmethod
    def validate_request_id(cls, value: object) -> str:
        return _identifier(value, field="request_id")

    @field_validator("tool_name", mode="before")
    @classmethod
    def validate_tool_name(cls, value: object) -> str:
        return _tool_name(value)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="summary")

    @model_validator(mode="after")
    def validate_result(self) -> "ToolResult":
        if self.status is not ToolResultStatus.SUCCESS and self.output is not None:
            raise ValueError("non-success result must not contain output")
        _validate_collections(self.artifacts, self.metrics)
        return self


class ToolAuditEvent(_ToolContract):
    event_type: ToolAuditEventType
    tool_name: str
    request_id: str
    caller: str
    timestamp: datetime

    @field_validator("tool_name", mode="before")
    @classmethod
    def validate_tool_name(cls, value: object) -> str:
        return _tool_name(value)

    @field_validator("request_id", "caller", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)
