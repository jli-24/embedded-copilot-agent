from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import (
    canonical_fingerprint,
    fingerprint,
    identifier,
    safe_text,
)


class ToolContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ToolType(StrEnum):
    ESP_IDF = "ESP-IDF"
    PLATFORMIO = "PLATFORMIO"
    OPENOCD = "OPENOCD"
    JLINK = "JLINK"
    SERIAL = "SERIAL"


class ToolExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class ToolCapabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ToolExecutionRequest(ToolContract):
    tool_type: ToolType
    operation: str
    workspace_reference: str | None = None
    artifact_reference: str | None = None
    approval_reference: str | None = None
    fingerprint: str

    @field_validator("operation", mode="before")
    @classmethod
    def validate_operation(cls, value: object) -> str:
        return identifier(value, field="operation")

    @field_validator(
        "workspace_reference", "artifact_reference", "approval_reference", mode="before"
    )
    @classmethod
    def validate_references(cls, value: object, info) -> str | None:
        if value is None:
            return None
        return identifier(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_request_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "ToolExecutionRequest":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("tool execution request fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "ToolExecutionRequest":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class ToolExecutionResult(ToolContract):
    status: ToolExecutionStatus
    tool_type: ToolType
    operation: str
    artifact_reference: str | None = None
    summary: str
    fingerprint: str

    @field_validator("operation", mode="before")
    @classmethod
    def validate_operation(cls, value: object) -> str:
        return identifier(value, field="operation")

    @field_validator("artifact_reference", mode="before")
    @classmethod
    def validate_artifact(cls, value: object) -> str | None:
        if value is None:
            return None
        return identifier(value, field="artifact_reference")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", maximum=512)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_result_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "ToolExecutionResult":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("tool execution result fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "ToolExecutionResult":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class ToolCapabilitySnapshot(ToolContract):
    tool_name: str
    version: str
    capabilities: tuple[str, ...] = Field(default=())
    status: ToolCapabilityStatus
    fingerprint: str

    @field_validator("tool_name", "version", mode="before")
    @classmethod
    def validate_names(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name, maximum=128)

    @field_validator("capabilities", mode="before")
    @classmethod
    def validate_capabilities(cls, value: object) -> tuple[str, ...]:
        if type(value) is not tuple:
            raise ValueError("capabilities must be a tuple")
        return tuple(identifier(item, field="capability") for item in value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_capability_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "ToolCapabilitySnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("tool capability fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "ToolCapabilitySnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class ToolStatusPort(Protocol):
    def get_snapshot(self, project_id: str) -> ToolCapabilitySnapshot | None: ...


@runtime_checkable
class ToolBuildPort(Protocol):
    def build(self, request: ToolExecutionRequest) -> ToolExecutionResult: ...


@runtime_checkable
class ToolFlashPort(Protocol):
    def flash(self, request: ToolExecutionRequest) -> ToolExecutionResult: ...


@runtime_checkable
class ToolDevicePort(Protocol):
    def get_snapshot(self, project_id: str) -> object | None: ...


def validate_execution_request(value: object) -> ToolExecutionRequest:
    if type(value) is not ToolExecutionRequest:
        raise TypeError("tool execution request is invalid")
    return ToolExecutionRequest.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_execution_result(value: object) -> ToolExecutionResult:
    if type(value) is not ToolExecutionResult:
        raise TypeError("tool execution result is invalid")
    return ToolExecutionResult.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_capability_snapshot(value: object) -> ToolCapabilitySnapshot:
    if type(value) is not ToolCapabilitySnapshot:
        raise TypeError("tool capability snapshot is invalid")
    return ToolCapabilitySnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "ToolBuildPort",
    "ToolCapabilitySnapshot",
    "ToolCapabilityStatus",
    "ToolContract",
    "ToolDevicePort",
    "ToolExecutionRequest",
    "ToolExecutionResult",
    "ToolExecutionStatus",
    "ToolFlashPort",
    "ToolStatusPort",
    "ToolType",
    "validate_capability_snapshot",
    "validate_execution_request",
    "validate_execution_result",
]
