from __future__ import annotations

import copy
import math
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.verification_agent import (
    VerificationStatus,
    VerificationSubjectType,
)

from .context import MemoryTrustBasis
from .exceptions import MemoryRetrievalUnavailable
from .models import (
    EngineeringDecisionMemory,
    EngineeringMemoryHistoryPage,
    EngineeringMemoryRecord,
    EngineeringMemorySnapshot,
    KnownIssueMemory,
    MemorySnapshotRecord,
    MemorySnapshotType,
    MemoryStatus,
    MemoryType,
    _identifier,
    _safe_derived_reference,
)


class _VerifiedReadContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} is invalid")  # noqa: TRY004
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


class VerifiedMemoryReadProjection(_VerifiedReadContract):
    record_id: str
    logical_key: str
    memory_type: MemoryType
    trust_basis: MemoryTrustBasis
    verification_subject: VerificationSubjectType | None
    confidence: float
    last_transition_at: datetime

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")

    @field_validator("logical_key", mode="before")
    @classmethod
    def validate_logical_key(cls, value: object) -> str:
        return _safe_derived_reference(value, field="logical_key")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("confidence is invalid")
        return value

    @field_validator("last_transition_at", mode="before")
    @classmethod
    def validate_last_transition_at(cls, value: object) -> datetime:
        return _utc(value, field="last_transition_at")

    @model_validator(mode="after")
    def validate_trust_projection(self) -> VerifiedMemoryReadProjection:
        if self.trust_basis is MemoryTrustBasis.VERIFICATION:
            if self.verification_subject is None or self.confidence != 1.0:
                raise ValueError("verification projection is invalid")
        elif self.verification_subject is not None or self.confidence != 0.5:
            raise ValueError("human approval projection is invalid")
        return self


def _revalidate(value: object, expected_type: type[BaseModel]) -> BaseModel:
    if not isinstance(value, expected_type):
        raise ValueError("read projection input is invalid")  # noqa: TRY004
    return expected_type.model_validate(copy.deepcopy(value))


def _history_records(
    *,
    snapshot: EngineeringMemorySnapshot,
    history_pages: tuple[EngineeringMemoryHistoryPage, ...],
) -> dict[str, EngineeringMemoryRecord]:
    if type(history_pages) is not tuple or not history_pages:
        raise ValueError("history pages are invalid")

    checked_pages = tuple(
        _revalidate(page, EngineeringMemoryHistoryPage) for page in history_pages
    )
    for index, page in enumerate(checked_pages):
        if (
            page.project_id != snapshot.project_id
            or page.memory_id != snapshot.memory_id
            or page.aggregate_revision != snapshot.aggregate_revision
            or (index < len(checked_pages) - 1 and not page.has_more)
            or (index == len(checked_pages) - 1 and page.has_more)
        ):
            raise ValueError("history page does not match snapshot")
        if page.next_cursor is not None and not page.next_cursor.startswith(
            f"revision:{snapshot.aggregate_revision}:offset:"
        ):
            raise ValueError("history cursor does not match snapshot")

    records = tuple(record for page in checked_pages for record in page.records)
    record_ids = tuple(record.record_id for record in records)
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("history record IDs must be unique")
    return {record.record_id: record for record in records}


def _record_matches_snapshot(
    snapshot_record: MemorySnapshotRecord,
    history_record: EngineeringMemoryRecord,
) -> bool:
    return (
        snapshot_record.record_id == history_record.record_id
        and snapshot_record.logical_key == history_record.logical_key
        and snapshot_record.memory_type is history_record.memory_type
        and snapshot_record.payload == history_record.payload
        and snapshot_record.provenance == history_record.provenance
        and snapshot_record.status is history_record.status
        and snapshot_record.record_revision == history_record.record_revision
        and snapshot_record.supersedes_record_id
        == history_record.supersedes_record_id
    )


def _verification_projection(
    record: EngineeringMemoryRecord,
) -> VerifiedMemoryReadProjection:
    transition = record.state_history[-1]
    binding_ids = tuple(
        item.verification_request_id for item in record.verification_bindings
    )
    if (
        transition.from_status is not MemoryStatus.CANDIDATE
        or transition.to_status is not MemoryStatus.VERIFIED
        or not record.verification_bindings
        or len(binding_ids) != len(set(binding_ids))
        or record.approval_binding is not None
    ):
        raise ValueError("verification trust binding is invalid")
    binding = record.verification_bindings[-1]
    if (
        transition.evidence_reference != binding.verification_request_id
        or binding.result_status is not VerificationStatus.PASS
        or binding.requested_at > transition.transitioned_at
    ):
        raise ValueError("verification trust binding is invalid")
    return VerifiedMemoryReadProjection(
        record_id=record.record_id,
        logical_key=record.logical_key,
        memory_type=record.memory_type,
        trust_basis=MemoryTrustBasis.VERIFICATION,
        verification_subject=binding.subject_type,
        confidence=1.0,
        last_transition_at=record.last_transition_at,
    )


def _approval_projection(
    record: EngineeringMemoryRecord,
) -> VerifiedMemoryReadProjection:
    transition = record.state_history[-1]
    approval = record.approval_binding
    if (
        transition.from_status is not MemoryStatus.CANDIDATE
        or transition.to_status is not MemoryStatus.VERIFIED
        or approval is None
        or not isinstance(record.payload, (EngineeringDecisionMemory, KnownIssueMemory))
        or transition.evidence_reference != approval.approval_id
        or approval.record_id != record.record_id
        or approval.record_revision != record.record_revision - 1
        or approval.approved_at > transition.transitioned_at
    ):
        raise ValueError("human approval trust binding is invalid")
    return VerifiedMemoryReadProjection(
        record_id=record.record_id,
        logical_key=record.logical_key,
        memory_type=record.memory_type,
        trust_basis=MemoryTrustBasis.HUMAN_APPROVAL,
        verification_subject=None,
        confidence=0.5,
        last_transition_at=record.last_transition_at,
    )


def _project_record(
    *,
    snapshot_record: MemorySnapshotRecord,
    history_record: EngineeringMemoryRecord,
    snapshot_revision: int,
    requested_at: datetime,
) -> VerifiedMemoryReadProjection:
    if (
        snapshot_record.status is not MemoryStatus.VERIFIED
        or history_record.status is not MemoryStatus.VERIFIED
        or not _record_matches_snapshot(snapshot_record, history_record)
        or history_record.created_aggregate_revision > snapshot_revision
        or history_record.last_updated_aggregate_revision > snapshot_revision
        or history_record.last_transition_at > requested_at
    ):
        raise ValueError("verified record projection is invalid")

    evidence_type = history_record.state_history[-1].evidence_type
    if evidence_type == "VERIFICATION":
        return _verification_projection(history_record)
    if evidence_type == "HUMAN_APPROVAL":
        return _approval_projection(history_record)
    raise ValueError("verified record trust basis is invalid")


def project_verified_memory_read(
    *,
    snapshot: EngineeringMemorySnapshot,
    history_pages: tuple[EngineeringMemoryHistoryPage, ...],
    requested_at: datetime,
) -> tuple[VerifiedMemoryReadProjection, ...]:
    try:
        checked_snapshot = _revalidate(snapshot, EngineeringMemorySnapshot)
        if checked_snapshot.snapshot_type is not MemorySnapshotType.VERIFIED:
            raise ValueError("snapshot must be verified")
        checked_requested_at = _utc(
            copy.deepcopy(requested_at),
            field="requested_at",
        )
        history_by_id = _history_records(
            snapshot=checked_snapshot,
            history_pages=history_pages,
        )
        snapshot_ids = tuple(record.record_id for record in checked_snapshot.records)
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("snapshot record IDs must be unique")

        projected = []
        for snapshot_record in checked_snapshot.records:
            history_record = history_by_id.get(snapshot_record.record_id)
            if history_record is None:
                raise ValueError("snapshot record is missing from history")
            if (
                history_record.project_id != checked_snapshot.project_id
                or history_record.memory_id != checked_snapshot.memory_id
            ):
                raise ValueError("history record identity is invalid")
            projected.append(
                _project_record(
                    snapshot_record=snapshot_record,
                    history_record=history_record,
                    snapshot_revision=checked_snapshot.aggregate_revision,
                    requested_at=checked_requested_at,
                )
            )
        return tuple(projected)
    except MemoryRetrievalUnavailable:
        raise
    except (TypeError, ValueError):
        raise MemoryRetrievalUnavailable() from None
