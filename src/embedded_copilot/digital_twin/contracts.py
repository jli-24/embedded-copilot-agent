from __future__ import annotations

import copy
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import (
    canonical_fingerprint,
    fingerprint,
    identifier,
    safe_text,
    tuple_only,
)


class DigitalTwinContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class MetricsProjection(DigitalTwinContract):
    cpu_usage: str
    memory_usage: str
    flash_usage: str
    ram_usage: str
    latency: str
    power_estimate: str
    communication_quality: str
    fingerprint: str

    @field_validator(
        "cpu_usage",
        "memory_usage",
        "flash_usage",
        "ram_usage",
        "latency",
        "power_estimate",
        "communication_quality",
        mode="before",
    )
    @classmethod
    def validate_values(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> MetricsProjection:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("metrics fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> MetricsProjection:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class ConstraintProjection(DigitalTwinContract):
    constraint_type: str
    reference: str
    status: str
    fingerprint: str

    @field_validator("constraint_type", "status", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return identifier(value, field="reference")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> ConstraintProjection:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("constraint fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> ConstraintProjection:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class DigitalTwinSnapshot(DigitalTwinContract):
    project_id: str
    hardware_reference: str
    firmware_reference: str
    device_reference: str
    validation_reference: str
    metrics: MetricsProjection
    constraints: tuple[ConstraintProjection, ...] = Field(max_length=128)
    fingerprint: str

    @field_validator(
        "project_id",
        "hardware_reference",
        "firmware_reference",
        "device_reference",
        "validation_reference",
        mode="before",
    )
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("constraints", mode="before")
    @classmethod
    def validate_constraints(cls, value: object) -> object:
        return tuple_only(value, field="constraints")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> DigitalTwinSnapshot:
        references = (
            self.hardware_reference,
            self.firmware_reference,
            self.device_reference,
            self.validation_reference,
        )
        if len(references) != len(set(references)):
            raise ValueError("twin references must be distinct")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("digital twin fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> DigitalTwinSnapshot:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class DigitalTwinPort(Protocol):
    def get_snapshot(self, project_id: str) -> DigitalTwinSnapshot | None: ...


DigitalTwinSnapshotPort = DigitalTwinPort


def validate_snapshot(value: object) -> DigitalTwinSnapshot:
    if type(value) is not DigitalTwinSnapshot:
        raise TypeError("digital twin snapshot is invalid")
    return DigitalTwinSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "ConstraintProjection",
    "DigitalTwinContract",
    "DigitalTwinPort",
    "DigitalTwinSnapshot",
    "DigitalTwinSnapshotPort",
    "MetricsProjection",
    "validate_snapshot",
]
