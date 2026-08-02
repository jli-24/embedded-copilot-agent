"""Typed Human Loop proof accepted by the Execution Runtime."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.human_loop import HumanReviewSnapshot, ProposalProjection

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$"
_FINGERPRINT = r"^sha256:[a-f0-9]{64}$"


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if re.fullmatch(_IDENTIFIER, candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _checked_fingerprint(value: object) -> str:
    if type(value) is not str or re.fullmatch(_FINGERPRINT, value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("approval_timestamp must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError("approval_timestamp must be timezone aware")
    return value.astimezone(UTC)


def execution_approval_fingerprint(
    *,
    execution_id: str,
    ready_snapshot_fingerprint: str,
    human_review: HumanReviewSnapshot,
    reviewer: str,
    approval_timestamp: datetime,
) -> str:
    encoded = json.dumps(
        {
            "approval_timestamp": approval_timestamp.isoformat(),
            "execution_id": execution_id,
            "human_review": human_review.model_dump(mode="json"),
            "ready_snapshot_fingerprint": ready_snapshot_fingerprint,
            "reviewer": reviewer,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class ExecutionApprovalContext(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
        hide_input_in_errors=True,
    )

    execution_id: str
    ready_snapshot_fingerprint: str
    human_review: HumanReviewSnapshot
    reviewer: str
    approval_timestamp: datetime
    fingerprint: str

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _ready_fingerprint = field_validator("ready_snapshot_fingerprint")(
        _checked_fingerprint
    )
    _reviewer = field_validator("reviewer")(
        lambda value: _identifier(value, field="reviewer")
    )
    _approval_timestamp = field_validator("approval_timestamp")(_utc)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("human_review", mode="before")
    @classmethod
    def _typed_review(cls, value: object) -> object:
        if type(value) is not HumanReviewSnapshot:
            raise ValueError("human_review must be a typed review snapshot")
        return value

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> ExecutionApprovalContext:
        if self.fingerprint != execution_approval_fingerprint(
            execution_id=self.execution_id,
            ready_snapshot_fingerprint=self.ready_snapshot_fingerprint,
            human_review=self.human_review,
            reviewer=self.reviewer,
            approval_timestamp=self.approval_timestamp,
        ):
            raise ValueError("approval fingerprint mismatch")
        return self


__all__ = (
    "ExecutionApprovalContext",
    "ProposalProjection",
    "execution_approval_fingerprint",
)
