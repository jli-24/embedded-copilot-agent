from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .models import canonical_fingerprint, fingerprint, identifier


class ValidationContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class LoopState(StrEnum):
    PENDING = "PENDING"
    BUILD_READY = "BUILD_READY"
    FLASH_PENDING = "FLASH_PENDING"
    FLASHING = "FLASHING"
    OBSERVING = "OBSERVING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class FlashState(StrEnum):
    PENDING = "PENDING"
    FLASHING = "FLASHING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class ObservationState(StrEnum):
    PENDING = "PENDING"
    OBSERVING = "OBSERVING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class VerificationState(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ValidationSnapshot(ValidationContract):
    project_id: str
    firmware_reference: str
    device_reference: str
    build_status: LoopState
    flash_status: FlashState
    observation_status: ObservationState
    verification_status: VerificationState
    fingerprint: str

    @field_validator(
        "project_id", "firmware_reference", "device_reference", mode="before"
    )
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "ValidationSnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("validation snapshot fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "ValidationSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class ValidationSnapshotPort(Protocol):
    def get_snapshot(self, project_id: str) -> ValidationSnapshot | None: ...


def validation_snapshot_fingerprint(value: ValidationSnapshot) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def validate_validation_snapshot(value: object) -> ValidationSnapshot:
    if type(value) is not ValidationSnapshot:
        raise TypeError("validation snapshot is invalid")
    return ValidationSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )
