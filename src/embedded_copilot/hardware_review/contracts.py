from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import field_validator, model_validator

from embedded_copilot.hardware_design.models import UnifiedHardwareModel, V22Contract
from .models import (
    _v22_canonical,
    _v22_fingerprint,
    review_evidence,
    review_summary,
)


class HardwareReviewCategory(StrEnum):
    POWER = "POWER"
    SIGNAL = "SIGNAL"
    GPIO = "GPIO"
    COMPONENT = "COMPONENT"
    LAYOUT = "LAYOUT"
    MANUFACTURING = "MANUFACTURING"


class HardwareReviewSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class HardwareReviewStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    UNVERIFIED = "UNVERIFIED"


class HardwareReviewProposal(V22Contract):
    review_id: str
    project_id: str
    category: HardwareReviewCategory
    severity: HardwareReviewSeverity
    summary: str
    evidence_reference: str
    status: HardwareReviewStatus
    fingerprint: str

    @field_validator("review_id", "project_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        from embedded_copilot.hardware_design.models import _v22_id

        return _v22_id(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return review_summary(value)

    @field_validator("evidence_reference", mode="before")
    @classmethod
    def validate_evidence(cls, value: object) -> str:
        return review_evidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return _v22_fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "HardwareReviewProposal":
        if self.fingerprint != _v22_canonical(self, exclude={"fingerprint"}):
            raise ValueError("hardware review fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "HardwareReviewProposal":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = _v22_canonical(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


@runtime_checkable
class HardwareReviewPort(Protocol):
    def get_snapshot(
        self, project_id: str
    ) -> tuple[HardwareReviewProposal, ...] | None: ...


def validate_review_proposal(value: object) -> HardwareReviewProposal:
    if type(value) is not HardwareReviewProposal:
        raise TypeError("hardware review proposal is invalid")
    return HardwareReviewProposal.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_review_proposals(value: object) -> tuple[HardwareReviewProposal, ...]:
    if type(value) is not tuple:
        raise TypeError("hardware review proposals must be a tuple")
    checked = tuple(validate_review_proposal(item) for item in value)
    ids = tuple(item.review_id for item in checked)
    if len(ids) != len(set(ids)):
        raise ValueError("hardware review identifiers must be unique")
    return checked


__all__ = [
    "HardwareReviewCategory",
    "HardwareReviewPort",
    "HardwareReviewProposal",
    "HardwareReviewSeverity",
    "HardwareReviewStatus",
    "UnifiedHardwareModel",
    "validate_review_proposal",
    "validate_review_proposals",
]
