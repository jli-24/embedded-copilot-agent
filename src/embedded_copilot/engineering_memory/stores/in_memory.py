from __future__ import annotations

import copy
from dataclasses import dataclass
from threading import RLock

from ..exceptions import (
    MemoryOperationConflict,
    MemoryRecordNotFound,
    MemoryRevisionConflict,
    MemoryStateTransitionRejected,
)
from ..fingerprint import canonical_data_fingerprint, canonical_fingerprint
from ..models import (
    AffectedMemoryRecord,
    ApplyHumanApprovalRequest,
    ApplyVerificationRequest,
    CreateCandidateRequest,
    CreateReplacementCandidateRequest,
    EngineeringDecisionMemory,
    EngineeringMemoryHistoryPage,
    EngineeringMemoryRecord,
    EngineeringMemorySnapshot,
    GetCandidateSnapshotRequest,
    GetHistoryRequest,
    GetVerifiedSnapshotRequest,
    KnownIssueMemory,
    MemoryMutationOutcome,
    MemoryMutationResult,
    MemorySnapshotRecord,
    MemorySnapshotType,
    MemoryStateTransition,
    MemoryStatus,
    MemoryType,
    RevokeRecordRequest,
    VerificationEvidenceBinding,
    VerificationHistoryMemory,
    VerificationStatus,
)
from ..rules import (
    build_candidate_record,
    logical_key_for,
    memory_context_id,
    verification_subject_is_compatible,
)


@dataclass(frozen=True)
class _OperationReceipt:
    request_fingerprint: str
    result: MemoryMutationResult


@dataclass(frozen=True)
class _Aggregate:
    project_id: str
    memory_id: str
    aggregate_revision: int
    records: dict[str, EngineeringMemoryRecord]
    active_verified_by_logical_key: dict[str, str]
    candidate_by_logical_key: dict[str, str]
    operation_receipts: dict[str, _OperationReceipt]
    verification_request_ids: frozenset[str]
    approval_ids: frozenset[str]


def _empty_aggregate(project_id: str, memory_id: str) -> _Aggregate:
    return _Aggregate(
        project_id, memory_id, 0, {}, {}, {}, {}, frozenset(), frozenset()
    )


def _checked_fingerprint(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise MemoryOperationConflict()
    return value


def _revalidate(value):
    return type(value).model_validate(copy.deepcopy(value))


def _replay(
    aggregate: _Aggregate, operation_id: str, request_fingerprint: str
) -> MemoryMutationResult | None:
    receipt = aggregate.operation_receipts.get(operation_id)
    if receipt is None:
        return None
    if receipt.request_fingerprint != request_fingerprint:
        raise MemoryOperationConflict()
    return _revalidate(receipt.result)


def _require_revision(aggregate: _Aggregate, expected_revision: int) -> None:
    if aggregate.aggregate_revision != expected_revision:
        raise MemoryRevisionConflict()


def _affected(record: EngineeringMemoryRecord) -> AffectedMemoryRecord:
    return AffectedMemoryRecord(
        record_id=record.record_id,
        status=record.status,
        record_revision=record.record_revision,
    )


def _result(request, outcome, revision, records) -> MemoryMutationResult:
    return MemoryMutationResult(
        request_id=request.request_id,
        operation_id=request.operation_id,
        command_type=request.command_type,
        outcome=outcome,
        affected_records=tuple(
            _affected(item)
            for item in sorted(records, key=lambda record: record.record_id)
        ),
        aggregate_revision=revision,
    )


def _transition(
    record: EngineeringMemoryRecord,
    *,
    request,
    to_status: MemoryStatus,
    evidence_type: str,
    evidence_reference: str,
    reason_code: str,
    aggregate_revision: int,
    verification_binding: VerificationEvidenceBinding | None = None,
    approval_binding=None,
    superseded_by_record_id: str | None = None,
) -> EngineeringMemoryRecord:
    transition = MemoryStateTransition(
        from_status=record.status,
        to_status=to_status,
        request_id=request.request_id,
        operation_id=request.operation_id,
        evidence_type=evidence_type,
        evidence_reference=evidence_reference,
        reason_code=reason_code,
        transitioned_at=request.requested_at,
    )
    bindings = record.verification_bindings
    if verification_binding is not None:
        bindings += (verification_binding,)
    updated = record.model_copy(
        update={
            "status": to_status,
            "record_revision": record.record_revision + 1,
            "last_updated_aggregate_revision": aggregate_revision,
            "last_transition_at": request.requested_at,
            "verification_bindings": bindings,
            "approval_binding": (
                approval_binding
                if approval_binding is not None
                else record.approval_binding
            ),
            "state_history": record.state_history + (transition,),
            "superseded_by_record_id": (
                superseded_by_record_id
                if superseded_by_record_id is not None
                else record.superseded_by_record_id
            ),
        }
    )
    return EngineeringMemoryRecord.model_validate(updated)


def _snapshot_record(record: EngineeringMemoryRecord) -> MemorySnapshotRecord:
    return MemorySnapshotRecord(
        record_id=record.record_id,
        memory_type=record.memory_type,
        logical_key=record.logical_key,
        payload=record.payload,
        provenance=record.provenance,
        status=record.status,
        record_revision=record.record_revision,
        supersedes_record_id=record.supersedes_record_id,
    )


class InMemoryEngineeringMemoryStore:
    __slots__ = ("_aggregates", "_lock")

    def __init__(self) -> None:
        self._aggregates: dict[tuple[str, str], _Aggregate] = {}
        self._lock = RLock()

    def _load(self, project_id: str, memory_id: str) -> _Aggregate:
        return self._aggregates.get(
            (project_id, memory_id), _empty_aggregate(project_id, memory_id)
        )

    def _publish(
        self,
        aggregate: _Aggregate,
        *,
        request,
        request_fingerprint: str,
        records,
        verified,
        candidates,
        result: MemoryMutationResult,
        verification_ids=None,
        approval_ids=None,
    ) -> MemoryMutationResult:
        receipts = dict(aggregate.operation_receipts)
        receipts[request.operation_id] = _OperationReceipt(request_fingerprint, result)
        updated = _Aggregate(
            aggregate.project_id,
            aggregate.memory_id,
            result.aggregate_revision,
            records,
            verified,
            candidates,
            receipts,
            (
                aggregate.verification_request_ids
                if verification_ids is None
                else verification_ids
            ),
            aggregate.approval_ids if approval_ids is None else approval_ids,
        )
        self._aggregates[(aggregate.project_id, aggregate.memory_id)] = updated
        return _revalidate(result)

    def create_candidate(
        self, request: CreateCandidateRequest, *, request_fingerprint: str
    ) -> MemoryMutationResult:
        request = _revalidate(request)
        request_fingerprint = _checked_fingerprint(request_fingerprint)
        with self._lock:
            aggregate = self._load(request.project_id, request.memory_id)
            replay = _replay(aggregate, request.operation_id, request_fingerprint)
            if replay is not None:
                return replay
            _require_revision(aggregate, request.expected_revision)
            if request.record_id in aggregate.records:
                raise MemoryStateTransitionRejected()
            logical_key = logical_key_for(request.payload)
            verification_ids = aggregate.verification_request_ids
            candidates = dict(aggregate.candidate_by_logical_key)
            if isinstance(request.payload, VerificationHistoryMemory):
                identity = request.payload.verification_request_id
                if identity in verification_ids:
                    raise MemoryStateTransitionRejected()
                verification_ids = verification_ids | {identity}
            else:
                if (
                    logical_key in aggregate.active_verified_by_logical_key
                    or logical_key in candidates
                ):
                    raise MemoryStateTransitionRejected()
                candidates[logical_key] = request.record_id
            revision = aggregate.aggregate_revision + 1
            record = build_candidate_record(
                request_id=request.request_id,
                operation_id=request.operation_id,
                project_id=request.project_id,
                memory_id=request.memory_id,
                record_id=request.record_id,
                payload=request.payload,
                provenance=request.provenance,
                requested_at=request.requested_at,
                aggregate_revision=revision,
            )
            records = dict(aggregate.records)
            records[record.record_id] = record
            result = _result(
                request, MemoryMutationOutcome.CREATED, revision, (record,)
            )
            return self._publish(
                aggregate,
                request=request,
                request_fingerprint=request_fingerprint,
                records=records,
                verified=dict(aggregate.active_verified_by_logical_key),
                candidates=candidates,
                verification_ids=verification_ids,
                result=result,
            )

    def create_replacement_candidate(
        self,
        request: CreateReplacementCandidateRequest,
        *,
        request_fingerprint: str,
    ) -> MemoryMutationResult:
        request = _revalidate(request)
        request_fingerprint = _checked_fingerprint(request_fingerprint)
        with self._lock:
            aggregate = self._load(request.project_id, request.memory_id)
            replay = _replay(aggregate, request.operation_id, request_fingerprint)
            if replay is not None:
                return replay
            _require_revision(aggregate, request.expected_revision)
            if request.record_id in aggregate.records or isinstance(
                request.payload, VerificationHistoryMemory
            ):
                raise MemoryStateTransitionRejected()
            old = aggregate.records.get(request.supersedes_record_id)
            logical_key = logical_key_for(request.payload)
            if (
                old is None
                or old.status is not MemoryStatus.VERIFIED
                or old.logical_key != logical_key
                or aggregate.active_verified_by_logical_key.get(logical_key)
                != old.record_id
                or logical_key in aggregate.candidate_by_logical_key
            ):
                raise MemoryStateTransitionRejected()
            revision = aggregate.aggregate_revision + 1
            record = build_candidate_record(
                request_id=request.request_id,
                operation_id=request.operation_id,
                project_id=request.project_id,
                memory_id=request.memory_id,
                record_id=request.record_id,
                payload=request.payload,
                provenance=request.provenance,
                requested_at=request.requested_at,
                aggregate_revision=revision,
                supersedes_record_id=old.record_id,
            )
            records = dict(aggregate.records)
            records[record.record_id] = record
            candidates = dict(aggregate.candidate_by_logical_key)
            candidates[logical_key] = record.record_id
            result = _result(
                request, MemoryMutationOutcome.CREATED, revision, (record,)
            )
            return self._publish(
                aggregate,
                request=request,
                request_fingerprint=request_fingerprint,
                records=records,
                verified=dict(aggregate.active_verified_by_logical_key),
                candidates=candidates,
                result=result,
            )

    def _activate(
        self,
        aggregate,
        record,
        *,
        request,
        evidence_type,
        evidence_reference,
        reason_code,
        revision,
        verification_binding=None,
        approval_binding=None,
    ):
        records = dict(aggregate.records)
        verified = dict(aggregate.active_verified_by_logical_key)
        candidates = dict(aggregate.candidate_by_logical_key)
        new = _transition(
            record,
            request=request,
            to_status=MemoryStatus.VERIFIED,
            evidence_type=evidence_type,
            evidence_reference=evidence_reference,
            reason_code=reason_code,
            aggregate_revision=revision,
            verification_binding=verification_binding,
            approval_binding=approval_binding,
        )
        affected = (new,)
        if record.supersedes_record_id is not None:
            old = records.get(record.supersedes_record_id)
            if (
                old is None
                or old.status is not MemoryStatus.VERIFIED
                or verified.get(record.logical_key) != old.record_id
            ):
                raise MemoryStateTransitionRejected()
            old = _transition(
                old,
                request=request,
                to_status=MemoryStatus.SUPERSEDED,
                evidence_type=evidence_type,
                evidence_reference=evidence_reference,
                reason_code="REPLACED_BY_VERIFIED_RECORD",
                aggregate_revision=revision,
                superseded_by_record_id=new.record_id,
            )
            records[old.record_id] = old
            affected = (old, new)
        records[new.record_id] = new
        verified[new.logical_key] = new.record_id
        candidates.pop(new.logical_key, None)
        return records, verified, candidates, affected

    def apply_verification(
        self, request: ApplyVerificationRequest, *, request_fingerprint: str
    ) -> MemoryMutationResult:
        request = _revalidate(request)
        request_fingerprint = _checked_fingerprint(request_fingerprint)
        with self._lock:
            aggregate = self._load(request.project_id, request.memory_id)
            replay = _replay(aggregate, request.operation_id, request_fingerprint)
            if replay is not None:
                return replay
            _require_revision(aggregate, request.expected_revision)
            record = aggregate.records.get(request.record_id)
            if (
                record is None
                or record.status is not MemoryStatus.CANDIDATE
                or record.record_revision != request.record_revision
                or request.verification_request.context_id
                != memory_context_id(
                    request.project_id,
                    request.memory_id,
                    request.record_id,
                    request.record_revision,
                )
                or not verification_subject_is_compatible(
                    record, request.verification_request.subject_type
                )
                or any(
                    item.verification_request_id
                    == request.verification_request.request_id
                    for item in record.verification_bindings
                )
            ):
                raise MemoryStateTransitionRejected()
            revision = aggregate.aggregate_revision + 1
            binding = VerificationEvidenceBinding(
                verification_request_id=request.verification_request.request_id,
                subject_type=request.verification_request.subject_type,
                result_status=request.verification_result.status,
                request_fingerprint=canonical_fingerprint(request.verification_request),
                result_fingerprint=canonical_fingerprint(request.verification_result),
                requested_at=request.verification_request.requested_at,
                summary_reference=request.verification_result.request_id,
            )
            status = request.verification_result.status
            if status is VerificationStatus.PASS:
                records, verified, candidates, affected = self._activate(
                    aggregate,
                    record,
                    request=request,
                    evidence_type="VERIFICATION",
                    evidence_reference=binding.verification_request_id,
                    reason_code="VERIFICATION_PASSED",
                    revision=revision,
                    verification_binding=binding,
                )
            else:
                target = (
                    MemoryStatus.REJECTED
                    if status is VerificationStatus.FAIL
                    else MemoryStatus.CANDIDATE
                )
                changed = _transition(
                    record,
                    request=request,
                    to_status=target,
                    evidence_type="VERIFICATION",
                    evidence_reference=binding.verification_request_id,
                    reason_code=(
                        "VERIFICATION_FAILED"
                        if target is MemoryStatus.REJECTED
                        else "VERIFICATION_REVIEW_REQUIRED"
                    ),
                    aggregate_revision=revision,
                    verification_binding=binding,
                )
                records = dict(aggregate.records)
                records[changed.record_id] = changed
                verified = dict(aggregate.active_verified_by_logical_key)
                candidates = dict(aggregate.candidate_by_logical_key)
                if target is MemoryStatus.REJECTED:
                    candidates.pop(changed.logical_key, None)
                affected = (changed,)
            result = _result(
                request, MemoryMutationOutcome.TRANSITIONED, revision, affected
            )
            return self._publish(
                aggregate,
                request=request,
                request_fingerprint=request_fingerprint,
                records=records,
                verified=verified,
                candidates=candidates,
                result=result,
            )

    def apply_human_approval(
        self, request: ApplyHumanApprovalRequest, *, request_fingerprint: str
    ) -> MemoryMutationResult:
        request = _revalidate(request)
        request_fingerprint = _checked_fingerprint(request_fingerprint)
        with self._lock:
            aggregate = self._load(request.project_id, request.memory_id)
            replay = _replay(aggregate, request.operation_id, request_fingerprint)
            if replay is not None:
                return replay
            _require_revision(aggregate, request.expected_revision)
            record = aggregate.records.get(request.record_id)
            if (
                record is None
                or record.status is not MemoryStatus.CANDIDATE
                or record.record_revision != request.record_revision
                or not isinstance(
                    record.payload, (EngineeringDecisionMemory, KnownIssueMemory)
                )
                or request.approval.approval_id in aggregate.approval_ids
            ):
                raise MemoryStateTransitionRejected()
            revision = aggregate.aggregate_revision + 1
            records, verified, candidates, affected = self._activate(
                aggregate,
                record,
                request=request,
                evidence_type="HUMAN_APPROVAL",
                evidence_reference=request.approval.approval_id,
                reason_code=request.approval.reason_code,
                revision=revision,
                approval_binding=request.approval,
            )
            result = _result(
                request, MemoryMutationOutcome.TRANSITIONED, revision, affected
            )
            return self._publish(
                aggregate,
                request=request,
                request_fingerprint=request_fingerprint,
                records=records,
                verified=verified,
                candidates=candidates,
                approval_ids=aggregate.approval_ids | {request.approval.approval_id},
                result=result,
            )

    def revoke_record(
        self, request: RevokeRecordRequest, *, request_fingerprint: str
    ) -> MemoryMutationResult:
        request = _revalidate(request)
        request_fingerprint = _checked_fingerprint(request_fingerprint)
        with self._lock:
            aggregate = self._load(request.project_id, request.memory_id)
            replay = _replay(aggregate, request.operation_id, request_fingerprint)
            if replay is not None:
                return replay
            _require_revision(aggregate, request.expected_revision)
            record = aggregate.records.get(request.record_id)
            if record is None:
                raise MemoryRecordNotFound()
            if (
                record.record_revision != request.record_revision
                or record.status not in (MemoryStatus.CANDIDATE, MemoryStatus.VERIFIED)
            ):
                raise MemoryStateTransitionRejected()
            revision = aggregate.aggregate_revision + 1
            changed = _transition(
                record,
                request=request,
                to_status=MemoryStatus.REVOKED,
                evidence_type="REVOCATION",
                evidence_reference=request.reason_code,
                reason_code=request.reason_code,
                aggregate_revision=revision,
            )
            records = dict(aggregate.records)
            records[changed.record_id] = changed
            verified = dict(aggregate.active_verified_by_logical_key)
            candidates = dict(aggregate.candidate_by_logical_key)
            if record.status is MemoryStatus.VERIFIED:
                verified.pop(record.logical_key, None)
            else:
                candidates.pop(record.logical_key, None)
            result = _result(
                request, MemoryMutationOutcome.REVOKED, revision, (changed,)
            )
            return self._publish(
                aggregate,
                request=request,
                request_fingerprint=request_fingerprint,
                records=records,
                verified=verified,
                candidates=candidates,
                result=result,
            )

    def _snapshot(self, request, snapshot_type):
        request = _revalidate(request)
        with self._lock:
            aggregate = self._load(request.project_id, request.memory_id)
            status = (
                MemoryStatus.VERIFIED
                if snapshot_type is MemorySnapshotType.VERIFIED
                else MemoryStatus.CANDIDATE
            )
            selected = sorted(
                (
                    record
                    for record in aggregate.records.values()
                    if record.status is status
                ),
                key=lambda item: (item.logical_key, item.record_id),
            )
            categorized = {memory_type: [] for memory_type in MemoryType}
            for record in selected:
                categorized[record.memory_type].append(_snapshot_record(record))
            board_values = categorized[MemoryType.BOARD_PROFILE]
            data = {
                "request_id": request.request_id,
                "snapshot_type": snapshot_type,
                "project_id": request.project_id,
                "memory_id": request.memory_id,
                "aggregate_revision": aggregate.aggregate_revision,
                "board_profile": None if not board_values else board_values[0],
                "components": tuple(categorized[MemoryType.COMPONENT]),
                "pin_bindings": tuple(categorized[MemoryType.PIN_BINDING]),
                "interface_bindings": tuple(categorized[MemoryType.INTERFACE_BINDING]),
                "power_constraints": tuple(categorized[MemoryType.POWER_CONSTRAINT]),
                "engineering_decisions": tuple(
                    categorized[MemoryType.ENGINEERING_DECISION]
                ),
                "known_issues": tuple(categorized[MemoryType.KNOWN_ISSUE]),
                "verification_records": tuple(
                    categorized[MemoryType.VERIFICATION_HISTORY]
                ),
            }
            fingerprint_data = {}
            for key, value in data.items():
                if isinstance(value, MemorySnapshotRecord):
                    fingerprint_data[key] = value.model_dump(mode="json")
                elif isinstance(value, tuple):
                    fingerprint_data[key] = [
                        item.model_dump(mode="json") for item in value
                    ]
                elif isinstance(value, MemorySnapshotType):
                    fingerprint_data[key] = value.value
                else:
                    fingerprint_data[key] = value
            snapshot = EngineeringMemorySnapshot(
                **data,
                snapshot_fingerprint=canonical_data_fingerprint(fingerprint_data),
            )
            return _revalidate(snapshot)

    def get_verified_snapshot(
        self, request: GetVerifiedSnapshotRequest
    ) -> EngineeringMemorySnapshot:
        return self._snapshot(request, MemorySnapshotType.VERIFIED)

    def get_candidate_snapshot(
        self, request: GetCandidateSnapshotRequest
    ) -> EngineeringMemorySnapshot:
        return self._snapshot(request, MemorySnapshotType.CANDIDATE)

    def get_history(self, request: GetHistoryRequest) -> EngineeringMemoryHistoryPage:
        request = _revalidate(request)
        with self._lock:
            aggregate = self._load(request.project_id, request.memory_id)
            offset = 0
            if request.cursor is not None:
                _, revision_text, _, offset_text = request.cursor.split(":")
                if int(revision_text) != aggregate.aggregate_revision:
                    raise MemoryRevisionConflict()
                offset = int(offset_text)
            records = sorted(
                aggregate.records.values(),
                key=lambda item: (item.created_aggregate_revision, item.record_id),
            )
            page_records = tuple(
                _revalidate(item) for item in records[offset : offset + request.limit]
            )
            next_offset = offset + len(page_records)
            has_more = next_offset < len(records)
            page = EngineeringMemoryHistoryPage(
                request_id=request.request_id,
                project_id=request.project_id,
                memory_id=request.memory_id,
                aggregate_revision=aggregate.aggregate_revision,
                records=page_records,
                next_cursor=(
                    f"revision:{aggregate.aggregate_revision}:offset:{next_offset}"
                    if has_more
                    else None
                ),
                has_more=has_more,
            )
            return _revalidate(page)
