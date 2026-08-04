from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .models import canonical_fingerprint, fingerprint, identifier, safe_text
from .exceptions import (
    FlashApprovalRequired,
    FlashCapabilityRequired,
    FlashFailed,
    FlashUnavailable,
)


class FlashContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class FlashStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class FlashCapability(FlashContract):
    capability_reference: str

    @field_validator("capability_reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return identifier(value, field="capability_reference")


class FlashRequest(FlashContract):
    firmware_reference: str
    device_reference: str
    approval_reference: str | None = None
    capability_reference: str | None = None

    @field_validator("firmware_reference", "device_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("approval_reference", "capability_reference", mode="before")
    @classmethod
    def validate_optional_refs(cls, value: object, info) -> str | None:
        if value is None:
            return None
        return identifier(value, field=info.field_name)


class FlashResult(FlashContract):
    status: FlashStatus
    firmware_reference: str
    device_reference: str
    summary: str
    fingerprint: str

    @field_validator("firmware_reference", "device_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", maximum=512)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "FlashResult":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("flash result fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "FlashResult":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class FlashExecutorPort(Protocol):
    def flash(self, request: FlashRequest) -> FlashResult: ...


class FlashPort:
    def flash(self, request: FlashRequest) -> FlashResult:
        raise FlashUnavailable()


def flash_result_fingerprint(value: FlashResult) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def validate_flash_request(value: object) -> FlashRequest:
    if type(value) is not FlashRequest:
        raise TypeError("flash request is invalid")
    return FlashRequest.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_flash_result(value: object) -> FlashResult:
    if type(value) is not FlashResult:
        raise TypeError("flash result is invalid")
    return FlashResult.model_validate(copy.deepcopy(value.model_dump(mode="python")))


class ApprovedFlashPort(FlashPort):
    """Controlled boundary; external execution is only supplied through an executor."""

    __slots__ = ("_executor",)

    def __init__(self, executor: FlashExecutorPort | None = None) -> None:
        self._executor = executor

    def flash(self, request: FlashRequest) -> FlashResult:
        checked = validate_flash_request(request)
        if checked.capability_reference is None:
            raise FlashCapabilityRequired()
        if checked.approval_reference is None:
            raise FlashApprovalRequired()
        if self._executor is None:
            raise FlashUnavailable()
        try:
            return validate_flash_result(self._executor.flash(copy.deepcopy(checked)))
        except (
            FlashCapabilityRequired,
            FlashApprovalRequired,
            FlashUnavailable,
            FlashFailed,
        ):
            raise
        except Exception as error:
            raise FlashFailed() from error


__all__ = [
    "ApprovedFlashPort",
    "FlashCapability",
    "FlashExecutorPort",
    "FlashPort",
    "FlashRequest",
    "FlashResult",
    "FlashStatus",
    "flash_result_fingerprint",
    "validate_flash_request",
    "validate_flash_result",
]
