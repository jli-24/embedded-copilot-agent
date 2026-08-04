from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .models import canonical_fingerprint, fingerprint, identifier


class DeviceContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class DeviceType(StrEnum):
    ESP32 = "ESP32"
    STM32 = "STM32"
    UNKNOWN = "UNKNOWN"


class ConnectionStatus(StrEnum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    UNAVAILABLE = "UNAVAILABLE"


class DeviceConnection(DeviceContract):
    device_id: str
    device_type: DeviceType
    connection_status: ConnectionStatus
    fingerprint: str

    @field_validator("device_id", mode="before")
    @classmethod
    def validate_device_id(cls, value: object) -> str:
        return identifier(value, field="device_id")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "DeviceConnection":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("device connection fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "DeviceConnection":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class DeviceSnapshot(DeviceContract):
    project_id: str
    device_id: str
    device_type: DeviceType
    connection_status: ConnectionStatus
    fingerprint: str

    @field_validator("project_id", "device_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_snapshot_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "DeviceSnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("device snapshot fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "DeviceSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class DevicePort(Protocol):
    def connect(self, device_reference: str) -> DeviceConnection: ...


@runtime_checkable
class DeviceSnapshotPort(Protocol):
    def get_snapshot(self, project_id: str) -> DeviceSnapshot | None: ...


def device_connection_fingerprint(value: DeviceConnection) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def device_snapshot_fingerprint(value: DeviceSnapshot) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def validate_device_connection(value: object) -> DeviceConnection:
    if type(value) is not DeviceConnection:
        raise TypeError("device connection is invalid")
    return DeviceConnection.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_device_snapshot(value: object) -> DeviceSnapshot:
    if type(value) is not DeviceSnapshot:
        raise TypeError("device snapshot is invalid")
    return DeviceSnapshot.model_validate(copy.deepcopy(value.model_dump(mode="python")))


__all__ = [
    "ConnectionStatus",
    "DeviceConnection",
    "DeviceContract",
    "DevicePort",
    "DeviceSnapshot",
    "DeviceSnapshotPort",
    "DeviceType",
    "device_connection_fingerprint",
    "device_snapshot_fingerprint",
    "validate_device_connection",
    "validate_device_snapshot",
]
