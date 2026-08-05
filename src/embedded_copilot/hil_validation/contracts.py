from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import canonical_fingerprint, fingerprint, identifier, safe_text, tuple_only


class HILContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ObservationStatus(StrEnum):
    READY = "READY"
    CONNECTED = "CONNECTED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class HILTestStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


class HILOverallStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


class HardwareCapabilitySnapshot(HILContract):
    project_id: str
    device_reference: str
    board_type: str
    chip_family: str
    interfaces: tuple[str, ...] = Field(max_length=64)
    capabilities: tuple[str, ...] = Field(max_length=128)
    fingerprint: str

    @field_validator("project_id", "device_reference", mode="before")
    @classmethod
    def validate_references(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("board_type", "chip_family", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name, maximum=128)

    @field_validator("interfaces", "capabilities", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("interfaces", "capabilities")
    @classmethod
    def validate_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(identifier(item, field="capability") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("capabilities must be unique")
        return checked

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "HardwareCapabilitySnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("hardware capability fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "HardwareCapabilitySnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class MetricProjection(HILContract):
    name: str
    value: str

    @field_validator("name", "value", mode="before")
    @classmethod
    def validate_metric(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name, maximum=128)


class DeviceObservationSnapshot(HILContract):
    project_id: str
    device_reference: str
    observation_type: str
    status: ObservationStatus
    metrics: tuple[MetricProjection, ...] = Field(max_length=128)
    evidence_reference: str
    fingerprint: str

    @field_validator("project_id", "device_reference", "evidence_reference", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("observation_type", mode="before")
    @classmethod
    def validate_observation_type(cls, value: object) -> str:
        return safe_text(value, field="observation_type", maximum=128)

    @field_validator("metrics", mode="before")
    @classmethod
    def validate_metrics(cls, value: object) -> object:
        return tuple_only(value, field="metrics")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "DeviceObservationSnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("device observation fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "DeviceObservationSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class TestCaseProjection(HILContract):
    name: str
    status: HILTestStatus
    summary: str
    fingerprint: str

    @field_validator("name", "summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "TestCaseProjection":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("test case fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "TestCaseProjection":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class HILValidationRequest(HILContract):
    project_id: str
    device_reference: str
    firmware_reference: str
    approval_reference: str | None = None
    fingerprint: str

    @field_validator(
        "project_id", "device_reference", "firmware_reference", mode="before"
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("approval_reference", mode="before")
    @classmethod
    def validate_approval(cls, value: object) -> str | None:
        return None if value is None else identifier(value, field="approval_reference")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "HILValidationRequest":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("HIL request fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "HILValidationRequest":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class HILValidationResult(HILContract):
    project_id: str
    test_reference: str
    device_reference: str
    firmware_reference: str
    test_cases: tuple[TestCaseProjection, ...] = Field(max_length=128)
    overall_status: HILOverallStatus
    evidence_reference: str
    fingerprint: str

    @field_validator(
        "project_id", "test_reference", "device_reference", "firmware_reference",
        "evidence_reference", mode="before"
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("test_cases", mode="before")
    @classmethod
    def validate_cases(cls, value: object) -> object:
        return tuple_only(value, field="test_cases")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "HILValidationResult":
        names = tuple(case.name for case in self.test_cases)
        if len(names) != len(set(names)):
            raise ValueError("test case names must be unique")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("HIL result fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "HILValidationResult":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


@runtime_checkable
class HILAdapterPort(Protocol):
    def get_capability(self, device_reference: str) -> HardwareCapabilitySnapshot: ...

    def observe_device(self, device_reference: str) -> DeviceObservationSnapshot: ...

    def validate_firmware(self, request: HILValidationRequest) -> HILValidationResult: ...


@runtime_checkable
class HardwareCapabilitySnapshotPort(Protocol):
    def get_snapshot(self, project_id: str) -> HardwareCapabilitySnapshot | None: ...


@runtime_checkable
class DeviceObservationSnapshotPort(Protocol):
    def get_snapshot(self, project_id: str) -> DeviceObservationSnapshot | None: ...


@runtime_checkable
class HILValidationPort(Protocol):
    def validate(self, request: HILValidationRequest) -> HILValidationResult: ...

    def get_snapshot(self, project_id: str) -> HILValidationResult | None: ...


def _copy_validate(value: object, model: type[BaseModel], name: str):
    if type(value) is not model:
        raise TypeError(f"{name} is invalid")
    return model.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_capability_snapshot(value: object) -> HardwareCapabilitySnapshot:
    return _copy_validate(value, HardwareCapabilitySnapshot, "hardware capability snapshot")


def validate_observation_snapshot(value: object) -> DeviceObservationSnapshot:
    return _copy_validate(value, DeviceObservationSnapshot, "device observation snapshot")


def validate_request(value: object) -> HILValidationRequest:
    return _copy_validate(value, HILValidationRequest, "HIL request")


def validate_result(value: object) -> HILValidationResult:
    return _copy_validate(value, HILValidationResult, "HIL result")


__all__ = [
    "DeviceObservationSnapshot",
    "DeviceObservationSnapshotPort",
    "HILAdapterPort",
    "HILContract",
    "HILOverallStatus",
    "HILTestStatus",
    "HILValidationPort",
    "HILValidationRequest",
    "HILValidationResult",
    "HardwareCapabilitySnapshot",
    "HardwareCapabilitySnapshotPort",
    "MetricProjection",
    "ObservationStatus",
    "TestCaseProjection",
    "validate_capability_snapshot",
    "validate_observation_snapshot",
    "validate_request",
    "validate_result",
]
