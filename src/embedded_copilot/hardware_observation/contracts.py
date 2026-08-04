from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .models import canonical_fingerprint, fingerprint, identifier, safe_text


class ObservationContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class BootStatus(StrEnum):
    BOOTED = "BOOTED"
    NOT_BOOTED = "NOT_BOOTED"
    UNKNOWN = "UNKNOWN"


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ObservationSnapshot(ObservationContract):
    device_id: str
    boot_status: BootStatus
    firmware_version: str
    health_status: HealthStatus
    error_summary: str
    fingerprint: str

    @field_validator("device_id", mode="before")
    @classmethod
    def validate_device_id(cls, value: object) -> str:
        return identifier(value, field="device_id")

    @field_validator("firmware_version", mode="before")
    @classmethod
    def validate_version(cls, value: object) -> str:
        return safe_text(value, field="firmware_version", maximum=128)

    @field_validator("error_summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="error_summary", maximum=512, allow_empty=True)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "ObservationSnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("observation fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "ObservationSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class HardwareObservationPort(Protocol):
    def read(self, device_reference: str) -> ObservationSnapshot: ...


@runtime_checkable
class ObservationSnapshotPort(Protocol):
    def get_snapshot(self, project_id: str) -> ObservationSnapshot | None: ...


def observation_snapshot_fingerprint(value: ObservationSnapshot) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def validate_observation_snapshot(value: object) -> ObservationSnapshot:
    if type(value) is not ObservationSnapshot:
        raise TypeError("observation snapshot is invalid")
    return ObservationSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )
