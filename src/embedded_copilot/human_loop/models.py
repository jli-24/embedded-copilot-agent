"""Immutable contracts for the human-controlled review loop."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.engineering_generation import ArtifactType

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$"
_CHANGE_TOKEN = r"^[A-Z][A-Z0-9_]{2,63}$"
_FINGERPRINT = r"^sha256:[a-f0-9]{64}$"
_SENSITIVE = (
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])"
)
_ABSOLUTE_PATH = r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)"
_HTTPS_REFERENCE = r"^https://[^\s/@:]+(?::[0-9]{1,5})?(?:/[^\s]*)?$"


class _HumanLoopContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if re.fullmatch(_IDENTIFIER, candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _safe_text(value: object, *, field: str, maximum: int = 1024) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > maximum
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or re.search(_SENSITIVE, candidate, re.IGNORECASE) is not None
        or re.search(_ABSOLUTE_PATH, candidate) is not None
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _optional_safe_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _safe_text(value, field=field, maximum=1024)


def _change_token(value: object, *, field: str) -> str:
    if type(value) is not str or re.fullmatch(_CHANGE_TOKEN, value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _safe_reference(value: object) -> str:
    if type(value) is not str:
        raise ValueError("safe_reference is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if re.fullmatch(_IDENTIFIER, candidate) is not None:
        return candidate
    if (
        re.fullmatch(_HTTPS_REFERENCE, candidate) is not None
        and "?" not in candidate
        and "#" not in candidate
    ):
        return candidate
    raise ValueError("safe_reference is invalid")


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


def _tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _checked_fingerprint(value: object) -> str:
    if type(value) is not str or re.fullmatch(_FINGERPRINT, value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        encoded = value.astimezone(UTC).isoformat()
        return f"{encoded[:-6]}Z"
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        _jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class HumanReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"


class HumanLoopState(StrEnum):
    GENERATED = "GENERATED"
    WAITING_REVIEW = "WAITING_REVIEW"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    REJECTED = "REJECTED"


class HumanLoopProgressEventType(StrEnum):
    PROPOSAL_GENERATED = "PROPOSAL_GENERATED"
    REVIEW_WAITING = "REVIEW_WAITING"
    REVIEW_APPROVED = "REVIEW_APPROVED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    REVIEW_REJECTED = "REVIEW_REJECTED"


class FeedbackPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RevisionContextSource(StrEnum):
    KNOWLEDGE_CONTEXT = "KNOWLEDGE_CONTEXT"
    MEMORY_CONTEXT = "MEMORY_CONTEXT"


def proposal_projection_fingerprint(
    *,
    proposal_id: str,
    artifact_type: ArtifactType,
    artifact_version: int,
    summary: str,
    reference_ids: tuple[str, ...],
) -> str:
    return _fingerprint(
        {
            "proposal_id": proposal_id,
            "artifact_type": artifact_type,
            "artifact_version": artifact_version,
            "summary": summary,
            "reference_ids": reference_ids,
        }
    )


class ProposalProjection(_HumanLoopContract):
    proposal_id: str
    artifact_type: ArtifactType
    artifact_version: int
    summary: str
    reference_ids: tuple[str, ...]
    fingerprint: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=1024)
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("artifact_version")
    @classmethod
    def _version(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("artifact_version is invalid")
        return value

    @field_validator("reference_ids", mode="before")
    @classmethod
    def _reference_tuple(cls, value: object) -> object:
        return _tuple(value, field="reference_ids")

    @field_validator("reference_ids")
    @classmethod
    def _references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_identifier(item, field="reference_id") for item in value)
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("reference_ids must be sorted and unique")
        return checked

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> ProposalProjection:
        if self.fingerprint != proposal_projection_fingerprint(
            proposal_id=self.proposal_id,
            artifact_type=self.artifact_type,
            artifact_version=self.artifact_version,
            summary=self.summary,
            reference_ids=self.reference_ids,
        ):
            raise ValueError("fingerprint mismatch")
        return self


class ProposalResolutionRequest(_HumanLoopContract):
    proposal_id: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )


class HumanReviewRequest(_HumanLoopContract):
    proposal_id: str
    reviewer: str
    decision: HumanReviewDecision
    review_comment: str | None
    timestamp: datetime

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _reviewer = field_validator("reviewer")(
        lambda value: _identifier(value, field="reviewer")
    )
    _review_comment = field_validator("review_comment")(
        lambda value: _optional_safe_text(value, field="review_comment")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @model_validator(mode="after")
    def _comment_required_for_change(self) -> HumanReviewRequest:
        if (
            self.decision is HumanReviewDecision.CHANGES_REQUESTED
            and self.review_comment is None
        ):
            raise ValueError("review_comment is required")
        return self


class HumanReviewSubmissionRequest(_HumanLoopContract):
    proposal: ProposalProjection
    review: HumanReviewRequest


def human_review_decision_fingerprint(
    *,
    proposal_id: str,
    proposal_fingerprint: str,
    reviewer: str,
    decision: HumanReviewDecision,
    review_comment: str | None,
    timestamp: datetime,
) -> str:
    return _fingerprint(
        {
            "proposal_id": proposal_id,
            "proposal_fingerprint": proposal_fingerprint,
            "reviewer": reviewer,
            "decision": decision,
            "review_comment": review_comment,
            "timestamp": timestamp,
        }
    )


class HumanReviewDecisionProjection(_HumanLoopContract):
    proposal_id: str
    proposal_fingerprint: str
    reviewer: str
    decision: HumanReviewDecision
    review_comment: str | None
    timestamp: datetime
    fingerprint: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _proposal_fingerprint = field_validator("proposal_fingerprint")(
        _checked_fingerprint
    )
    _reviewer = field_validator("reviewer")(
        lambda value: _identifier(value, field="reviewer")
    )
    _review_comment = field_validator("review_comment")(
        lambda value: _optional_safe_text(value, field="review_comment")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> HumanReviewDecisionProjection:
        if self.fingerprint != human_review_decision_fingerprint(
            proposal_id=self.proposal_id,
            proposal_fingerprint=self.proposal_fingerprint,
            reviewer=self.reviewer,
            decision=self.decision,
            review_comment=self.review_comment,
            timestamp=self.timestamp,
        ):
            raise ValueError("fingerprint mismatch")
        return self


class FeedbackProjectionRequest(_HumanLoopContract):
    review: HumanReviewDecisionProjection
    timestamp: datetime

    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


def feedback_projection_fingerprint(
    *,
    proposal_id: str,
    review_fingerprint: str,
    change_type: str,
    target_reference: str,
    constraint: str,
    priority: FeedbackPriority,
    safe_reference: str,
) -> str:
    return _fingerprint(
        {
            "proposal_id": proposal_id,
            "review_fingerprint": review_fingerprint,
            "change_type": change_type,
            "target_reference": target_reference,
            "constraint": constraint,
            "priority": priority,
            "safe_reference": safe_reference,
        }
    )


class FeedbackProjection(_HumanLoopContract):
    proposal_id: str
    review_fingerprint: str
    change_type: str
    target_reference: str
    constraint: str
    priority: FeedbackPriority
    safe_reference: str
    fingerprint: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _review_fingerprint = field_validator("review_fingerprint")(_checked_fingerprint)
    _change_type = field_validator("change_type")(
        lambda value: _change_token(value, field="change_type")
    )
    _target_reference = field_validator("target_reference")(
        lambda value: _change_token(value, field="target_reference")
    )
    _constraint = field_validator("constraint")(
        lambda value: _change_token(value, field="constraint")
    )
    _safe_reference_value = field_validator("safe_reference")(_safe_reference)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> FeedbackProjection:
        if self.fingerprint != feedback_projection_fingerprint(
            proposal_id=self.proposal_id,
            review_fingerprint=self.review_fingerprint,
            change_type=self.change_type,
            target_reference=self.target_reference,
            constraint=self.constraint,
            priority=self.priority,
            safe_reference=self.safe_reference,
        ):
            raise ValueError("fingerprint mismatch")
        return self


class RevisionContextReference(_HumanLoopContract):
    source_type: RevisionContextSource
    reference_id: str
    fingerprint: str

    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)


def revision_context_fingerprint(
    *,
    proposal_fingerprint: str,
    feedback_fingerprint: str,
    context_references: tuple[RevisionContextReference, ...],
) -> str:
    return _fingerprint(
        {
            "proposal_fingerprint": proposal_fingerprint,
            "feedback_fingerprint": feedback_fingerprint,
            "context_references": context_references,
        }
    )


class RevisionContext(_HumanLoopContract):
    proposal_fingerprint: str
    feedback_fingerprint: str
    context_references: tuple[RevisionContextReference, ...]
    fingerprint: str

    _proposal_fingerprint = field_validator("proposal_fingerprint")(
        _checked_fingerprint
    )
    _feedback_fingerprint = field_validator("feedback_fingerprint")(
        _checked_fingerprint
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("context_references", mode="before")
    @classmethod
    def _reference_tuple(cls, value: object) -> object:
        return _tuple(value, field="context_references")

    @field_validator("context_references")
    @classmethod
    def _references(
        cls, value: tuple[RevisionContextReference, ...]
    ) -> tuple[RevisionContextReference, ...]:
        keys = tuple((item.source_type.value, item.reference_id) for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("context_references must be sorted and unique")
        return value

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> RevisionContext:
        if self.fingerprint != revision_context_fingerprint(
            proposal_fingerprint=self.proposal_fingerprint,
            feedback_fingerprint=self.feedback_fingerprint,
            context_references=self.context_references,
        ):
            raise ValueError("fingerprint mismatch")
        return self


class RevisionChange(_HumanLoopContract):
    target: str
    change: str

    _target = field_validator("target")(
        lambda value: _identifier(value, field="target")
    )
    _change = field_validator("change")(
        lambda value: _identifier(value, field="change")
    )


class RevisionPreparationRequest(_HumanLoopContract):
    revision_id: str
    proposal: ProposalProjection
    review: HumanReviewDecisionProjection
    feedback: FeedbackProjection
    context_references: tuple[RevisionContextReference, ...]
    timestamp: datetime

    _revision_id = field_validator("revision_id")(
        lambda value: _identifier(value, field="revision_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("context_references", mode="before")
    @classmethod
    def _reference_tuple(cls, value: object) -> object:
        return _tuple(value, field="context_references")

    @field_validator("context_references")
    @classmethod
    def _references(
        cls, value: tuple[RevisionContextReference, ...]
    ) -> tuple[RevisionContextReference, ...]:
        keys = tuple((item.source_type.value, item.reference_id) for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("context_references must be sorted and unique")
        return value


class RevisionGenerationRequest(_HumanLoopContract):
    revision_id: str
    base_proposal_id: str
    context: RevisionContext
    timestamp: datetime

    _revision_id = field_validator("revision_id")(
        lambda value: _identifier(value, field="revision_id")
    )
    _base_proposal_id = field_validator("base_proposal_id")(
        lambda value: _identifier(value, field="base_proposal_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


def revision_proposal_fingerprint(
    *,
    revision_id: str,
    base_proposal_id: str,
    changes: tuple[RevisionChange, ...],
    rationale_summary: str,
) -> str:
    return _fingerprint(
        {
            "revision_id": revision_id,
            "base_proposal_id": base_proposal_id,
            "changes": changes,
            "rationale_summary": rationale_summary,
        }
    )


class RevisionProposal(_HumanLoopContract):
    revision_id: str
    base_proposal_id: str
    changes: tuple[RevisionChange, ...]
    rationale_summary: str
    fingerprint: str

    _revision_id = field_validator("revision_id")(
        lambda value: _identifier(value, field="revision_id")
    )
    _base_proposal_id = field_validator("base_proposal_id")(
        lambda value: _identifier(value, field="base_proposal_id")
    )
    _rationale = field_validator("rationale_summary")(
        lambda value: _safe_text(value, field="rationale_summary", maximum=1024)
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("changes", mode="before")
    @classmethod
    def _change_tuple(cls, value: object) -> object:
        return _tuple(value, field="changes")

    @field_validator("changes")
    @classmethod
    def _changes(cls, value: tuple[RevisionChange, ...]) -> tuple[RevisionChange, ...]:
        keys = tuple((item.target, item.change) for item in value)
        if not value or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("changes must be sorted and unique")
        return value

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> RevisionProposal:
        if self.fingerprint != revision_proposal_fingerprint(
            revision_id=self.revision_id,
            base_proposal_id=self.base_proposal_id,
            changes=self.changes,
            rationale_summary=self.rationale_summary,
        ):
            raise ValueError("fingerprint mismatch")
        return self


class HumanLoopProgressEvent(_HumanLoopContract):
    sequence: int
    proposal_id: str
    state: HumanLoopState
    event: HumanLoopProgressEventType
    timestamp: datetime

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("sequence")
    @classmethod
    def _sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("sequence is invalid")
        return value


def human_review_snapshot_fingerprint(
    *,
    proposal: ProposalProjection,
    state: HumanLoopState,
    review: HumanReviewDecisionProjection,
    progress_sequence: int,
) -> str:
    return _fingerprint(
        {
            "proposal": proposal,
            "state": state,
            "review": review,
            "progress_sequence": progress_sequence,
        }
    )


class HumanReviewSnapshot(_HumanLoopContract):
    proposal_id: str
    proposal: ProposalProjection
    state: HumanLoopState
    review: HumanReviewDecisionProjection
    progress_sequence: int
    fingerprint: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("progress_sequence")
    @classmethod
    def _progress_sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("progress_sequence is invalid")
        return value

    @model_validator(mode="after")
    def _snapshot_matches(self) -> HumanReviewSnapshot:
        if (
            self.proposal_id != self.proposal.proposal_id
            or self.review.proposal_id != self.proposal_id
            or self.review.proposal_fingerprint != self.proposal.fingerprint
        ):
            raise ValueError("snapshot binding mismatch")
        if self.fingerprint != human_review_snapshot_fingerprint(
            proposal=self.proposal,
            state=self.state,
            review=self.review,
            progress_sequence=self.progress_sequence,
        ):
            raise ValueError("fingerprint mismatch")
        return self
