from __future__ import annotations

import copy
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .models import canonical_fingerprint, fingerprint, identifier, utc_datetime


class ApprovalContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalAction(ApprovalContract):
    action_id: str
    loop_id: str
    action_type: str
    action_fingerprint: str
    approval_status: ApprovalStatus
    fingerprint: str

    @field_validator("action_id", "loop_id", "action_type", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("action_fingerprint", "fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return fingerprint(value, field=info.field_name)

    @model_validator(mode="after")
    def verify(self) -> "ApprovalAction":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("approval action fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "ApprovalAction":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class ApprovalDecision(ApprovalContract):
    action_id: str
    action_fingerprint: str
    reviewer: str
    decided_at: datetime

    @field_validator("action_id", "reviewer", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("action_fingerprint", mode="before")
    @classmethod
    def validate_action_fingerprint(cls, value: object) -> str:
        return fingerprint(value, field="action_fingerprint")

    @field_validator("decided_at", mode="before")
    @classmethod
    def validate_decided_at(cls, value: object) -> object:
        return utc_datetime(value, field="decided_at")


@runtime_checkable
class ApprovalGatePort(Protocol):
    def get_action(self, action_id: str) -> ApprovalAction | None: ...

    def approve(self, decision: ApprovalDecision) -> ApprovalAction: ...

    def reject(self, decision: ApprovalDecision) -> ApprovalAction: ...

    def expire(self, action_id: str) -> ApprovalAction: ...


def approval_action_fingerprint(value: ApprovalAction) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def validate_approval_action(value: object) -> ApprovalAction:
    if type(value) is not ApprovalAction:
        raise TypeError("approval action is invalid")
    return ApprovalAction.model_validate(copy.deepcopy(value.model_dump(mode="python")))


__all__ = [
    "ApprovalAction",
    "ApprovalContract",
    "ApprovalDecision",
    "ApprovalGatePort",
    "ApprovalStatus",
    "approval_action_fingerprint",
    "validate_approval_action",
]
