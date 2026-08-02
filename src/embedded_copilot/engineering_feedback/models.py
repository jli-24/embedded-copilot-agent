"""Immutable contracts for the proposal-only Engineering Feedback Layer."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")


class _FeedbackContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value


def _fingerprint_value(value: object) -> str:
    if type(value) is not str or not _FINGERPRINT.fullmatch(value):
        raise ValueError("fingerprint is invalid")
    return value


def _safe_text(value: object, *, field: str, maximum: int = 512) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    normalized = unicodedata.normalize("NFC", value).strip()
    if (
        not normalized
        or len(normalized) > maximum
        or any(unicodedata.category(char).startswith("C") for char in normalized)
        or "\n" in normalized
        or "\r" in normalized
    ):
        raise ValueError(f"{field} is invalid")
    return normalized


def _tuple(value: object, *, field: str) -> tuple:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _constraints(value: object) -> tuple[str, ...]:
    items = _tuple(value, field="constraints")
    checked = tuple(
        item if type(item) is str and _TOKEN.fullmatch(item) else None for item in items
    )
    if (
        any(item is None for item in checked)
        or checked != tuple(sorted(checked))
        or len(checked) != len(set(checked))
        or len(checked) > 32
    ):
        raise ValueError("constraints must be sorted unique tokens")
    return checked  # type: ignore[return-value]


def _utc(value: object, *, field: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return {
            name: _jsonable(getattr(value, name)) for name in type(value).model_fields
        }
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite values are invalid")
    return value


def _fingerprint(kind: str, **values: object) -> str:
    encoded = json.dumps(
        _jsonable({"kind": kind, **values}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class FeedbackItemType(StrEnum):
    APPROVE = "APPROVE"
    REQUEST_CHANGE = "REQUEST_CHANGE"
    REJECT = "REJECT"
    COMMENT = "COMMENT"


class FeedbackTargetDomain(StrEnum):
    HARDWARE = "HARDWARE"
    FIRMWARE = "FIRMWARE"
    VALIDATION = "VALIDATION"
    EXECUTION = "EXECUTION"
    SYSTEM = "SYSTEM"


class EngineeringChangeType(StrEnum):
    ADD_REQUIREMENT = "ADD_REQUIREMENT"
    MODIFY_CONSTRAINT = "MODIFY_CONSTRAINT"
    REPLACE_COMPONENT = "REPLACE_COMPONENT"
    CHANGE_ARCHITECTURE = "CHANGE_ARCHITECTURE"
    OPTIMIZE_PARAMETER = "OPTIMIZE_PARAMETER"


class RevisionProposalState(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class FeedbackReviewOutcome(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMMENT_RECORDED = "COMMENT_RECORDED"
    CHANGES_PROPOSED = "CHANGES_PROPOSED"


class FeedbackFindingCode(StrEnum):
    CURRENT_RESULT_APPROVED = "CURRENT_RESULT_APPROVED"
    CURRENT_RESULT_REJECTED = "CURRENT_RESULT_REJECTED"
    COMMENT_RECORDED = "COMMENT_RECORDED"
    CHANGE_REQUESTED = "CHANGE_REQUESTED"
    REVISION_REVIEW_REQUIRED = "REVISION_REVIEW_REQUIRED"


_ITEM_KIND = {
    FeedbackItemType.APPROVE: "ApproveFeedbackItem",
    FeedbackItemType.REQUEST_CHANGE: "RequestChangeFeedbackItem",
    FeedbackItemType.REJECT: "RejectFeedbackItem",
    FeedbackItemType.COMMENT: "CommentFeedbackItem",
}


def feedback_item_fingerprint(**values: object) -> str:
    item_type = values.get("type")
    if type(item_type) is not FeedbackItemType:
        raise ValueError("feedback item type is invalid")
    return _fingerprint(_ITEM_KIND[item_type], **values)


class ApproveFeedbackItem(_FeedbackContract):
    type: Literal[FeedbackItemType.APPROVE] = FeedbackItemType.APPROVE
    target_reference: str
    reason: str
    constraints: tuple[str, ...]
    fingerprint: str

    _target = field_validator("target_reference")(_fingerprint_value)
    _reason = field_validator("reason")(lambda value: _safe_text(value, field="reason"))
    _constraint_values = field_validator("constraints", mode="before")(_constraints)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_item(self) -> ApproveFeedbackItem:
        if self.constraints:
            raise ValueError("approve constraints are invalid")
        if self.fingerprint != feedback_item_fingerprint(
            type=self.type,
            target_reference=self.target_reference,
            reason=self.reason,
            constraints=self.constraints,
        ):
            raise ValueError("feedback item fingerprint mismatch")
        return self


class RejectFeedbackItem(_FeedbackContract):
    type: Literal[FeedbackItemType.REJECT] = FeedbackItemType.REJECT
    target_reference: str
    reason: str
    constraints: tuple[str, ...]
    fingerprint: str

    _target = field_validator("target_reference")(_fingerprint_value)
    _reason = field_validator("reason")(lambda value: _safe_text(value, field="reason"))
    _constraint_values = field_validator("constraints", mode="before")(_constraints)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_item(self) -> RejectFeedbackItem:
        if self.constraints:
            raise ValueError("reject constraints are invalid")
        if self.fingerprint != feedback_item_fingerprint(
            type=self.type,
            target_reference=self.target_reference,
            reason=self.reason,
            constraints=self.constraints,
        ):
            raise ValueError("feedback item fingerprint mismatch")
        return self


class CommentFeedbackItem(_FeedbackContract):
    type: Literal[FeedbackItemType.COMMENT] = FeedbackItemType.COMMENT
    target_reference: str
    reason: str
    constraints: tuple[str, ...]
    fingerprint: str

    _target = field_validator("target_reference")(_fingerprint_value)
    _reason = field_validator("reason")(lambda value: _safe_text(value, field="reason"))
    _constraint_values = field_validator("constraints", mode="before")(_constraints)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_item(self) -> CommentFeedbackItem:
        if self.constraints:
            raise ValueError("comment constraints are invalid")
        if self.fingerprint != feedback_item_fingerprint(
            type=self.type,
            target_reference=self.target_reference,
            reason=self.reason,
            constraints=self.constraints,
        ):
            raise ValueError("feedback item fingerprint mismatch")
        return self


class RequestChangeFeedbackItem(_FeedbackContract):
    type: Literal[FeedbackItemType.REQUEST_CHANGE] = FeedbackItemType.REQUEST_CHANGE
    target_reference: str
    reason: str
    constraints: tuple[str, ...]
    change_id: str
    revision_id: str
    target_domain: FeedbackTargetDomain
    change_type: EngineeringChangeType
    fingerprint: str

    _target = field_validator("target_reference")(_fingerprint_value)
    _reason = field_validator("reason")(lambda value: _safe_text(value, field="reason"))
    _constraint_values = field_validator("constraints", mode="before")(_constraints)
    _change_id = field_validator("change_id")(
        lambda value: _identifier(value, field="change_id")
    )
    _revision_id = field_validator("revision_id")(
        lambda value: _identifier(value, field="revision_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_item(self) -> RequestChangeFeedbackItem:
        if not self.constraints:
            raise ValueError("request change constraints are required")
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != feedback_item_fingerprint(**values):
            raise ValueError("feedback item fingerprint mismatch")
        return self


FeedbackItem = Annotated[
    ApproveFeedbackItem
    | RequestChangeFeedbackItem
    | RejectFeedbackItem
    | CommentFeedbackItem,
    Field(discriminator="type"),
]


class EngineeringFeedbackProjection(_FeedbackContract):
    feedback_id: str
    artifact_contract_fingerprint: str
    artifact_source_fingerprint: str
    execution_report_fingerprint: str | None = None
    validation_report_fingerprint: str | None = None
    items: tuple[FeedbackItem, ...]
    submitted_at: datetime
    fingerprint: str

    _feedback_id = field_validator("feedback_id")(
        lambda value: _identifier(value, field="feedback_id")
    )
    _artifact = field_validator("artifact_contract_fingerprint")(_fingerprint_value)
    _source = field_validator("artifact_source_fingerprint")(_fingerprint_value)
    _submitted_at = field_validator("submitted_at")(
        lambda value: _utc(value, field="submitted_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("execution_report_fingerprint", "validation_report_fingerprint")
    @classmethod
    def validate_optional_fingerprint(cls, value: object) -> str | None:
        if value is None:
            return None
        return _fingerprint_value(value)

    @field_validator("items", mode="before")
    @classmethod
    def validate_items_tuple(cls, value: object) -> object:
        return _tuple(value, field="items")

    @model_validator(mode="after")
    def validate_projection(self) -> EngineeringFeedbackProjection:
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != engineering_feedback_projection_fingerprint(**values):
            raise ValueError("feedback projection fingerprint mismatch")
        return self


def engineering_feedback_projection_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringFeedbackProjection", **values)


class EngineeringChangeRequest(_FeedbackContract):
    change_id: str
    target_domain: FeedbackTargetDomain
    target_artifact_fingerprint: str
    change_type: EngineeringChangeType
    reason: str
    constraints: tuple[str, ...]
    fingerprint: str

    _change_id = field_validator("change_id")(
        lambda value: _identifier(value, field="change_id")
    )
    _target = field_validator("target_artifact_fingerprint")(_fingerprint_value)
    _reason = field_validator("reason")(lambda value: _safe_text(value, field="reason"))
    _constraint_values = field_validator("constraints", mode="before")(_constraints)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_change(self) -> EngineeringChangeRequest:
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != engineering_change_request_fingerprint(**values):
            raise ValueError("change request fingerprint mismatch")
        return self


def engineering_change_request_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringChangeRequest", **values)


class EngineeringRevisionProposal(_FeedbackContract):
    revision_id: str
    state: RevisionProposalState
    base_artifact_fingerprint: str
    change_request_fingerprint: str
    affected_domains: tuple[FeedbackTargetDomain, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _revision_id = field_validator("revision_id")(
        lambda value: _identifier(value, field="revision_id")
    )
    _base = field_validator("base_artifact_fingerprint")(_fingerprint_value)
    _change = field_validator("change_request_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("affected_domains", mode="before")
    @classmethod
    def validate_domains_tuple(cls, value: object) -> object:
        return _tuple(value, field="affected_domains")

    @model_validator(mode="after")
    def validate_revision(self) -> EngineeringRevisionProposal:
        order = {value: index for index, value in enumerate(FeedbackTargetDomain)}
        keys = tuple(order[item] for item in self.affected_domains)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("affected domains must be sorted and unique")
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != engineering_revision_proposal_fingerprint(**values):
            raise ValueError("revision proposal fingerprint mismatch")
        return self


def engineering_revision_proposal_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringRevisionProposal", **values)


class EngineeringFeedbackReviewProjection(_FeedbackContract):
    feedback_id: str
    outcome: FeedbackReviewOutcome
    item_count: int = Field(ge=1, le=64)
    change_request_count: int = Field(ge=0, le=64)
    revision_proposal_count: int = Field(ge=0, le=64)
    execution_report_fingerprint: str | None = None
    validation_report_fingerprint: str | None = None
    finding_codes: tuple[FeedbackFindingCode, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _feedback_id = field_validator("feedback_id")(
        lambda value: _identifier(value, field="feedback_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("execution_report_fingerprint", "validation_report_fingerprint")
    @classmethod
    def validate_optional_fingerprint(cls, value: object) -> str | None:
        if value is None:
            return None
        return _fingerprint_value(value)

    @field_validator("finding_codes", mode="before")
    @classmethod
    def validate_findings_tuple(cls, value: object) -> object:
        return _tuple(value, field="finding_codes")

    @model_validator(mode="after")
    def validate_review(self) -> EngineeringFeedbackReviewProjection:
        order = {value: index for index, value in enumerate(FeedbackFindingCode)}
        keys = tuple(order[item] for item in self.finding_codes)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("feedback findings must be sorted and unique")
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != engineering_feedback_review_fingerprint(**values):
            raise ValueError("feedback review fingerprint mismatch")
        return self


def engineering_feedback_review_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringFeedbackReviewProjection", **values)


class EngineeringFeedbackReport(_FeedbackContract):
    schema_version: Literal["1.0"] = "1.0"
    feedback: EngineeringFeedbackProjection
    change_requests: tuple[EngineeringChangeRequest, ...]
    revision_proposals: tuple[EngineeringRevisionProposal, ...]
    review: EngineeringFeedbackReviewProjection
    candidate_semantics: Literal["unverified"] = "unverified"
    review_required: Literal[True] = True
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("change_requests", "revision_proposals", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_report(self) -> EngineeringFeedbackReport:
        change_ids = tuple(item.change_id for item in self.change_requests)
        revision_ids = tuple(item.revision_id for item in self.revision_proposals)
        if change_ids != tuple(sorted(change_ids)) or len(change_ids) != len(
            set(change_ids)
        ):
            raise ValueError("change requests must be sorted and unique")
        if revision_ids != tuple(sorted(revision_ids)) or len(revision_ids) != len(
            set(revision_ids)
        ):
            raise ValueError("revision proposals must be sorted and unique")
        if (
            self.review.feedback_id != self.feedback.feedback_id
            or self.review.item_count != len(self.feedback.items)
            or self.review.change_request_count != len(self.change_requests)
            or self.review.revision_proposal_count != len(self.revision_proposals)
            or self.review.execution_report_fingerprint
            != self.feedback.execution_report_fingerprint
            or self.review.validation_report_fingerprint
            != self.feedback.validation_report_fingerprint
        ):
            raise ValueError("feedback report binding mismatch")
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name not in {"schema_version", "fingerprint"}
        }
        if self.fingerprint != engineering_feedback_report_fingerprint(**values):
            raise ValueError("feedback report fingerprint mismatch")
        return self


def engineering_feedback_report_fingerprint(**values: object) -> str:
    values.pop("schema_version", None)
    return _fingerprint("EngineeringFeedbackReport", **values)


def canonical_feedback_json(value: _FeedbackContract) -> str:
    return json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
