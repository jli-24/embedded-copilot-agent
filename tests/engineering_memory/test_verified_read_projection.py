from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_memory.context import MemoryTrustBasis
from embedded_copilot.engineering_memory.exceptions import MemoryRetrievalUnavailable
from embedded_copilot.engineering_memory.models import (
    ComponentMemory,
    EngineeringDecisionMemory,
    EngineeringMemoryHistoryPage,
    EngineeringMemoryRecord,
    EngineeringMemorySnapshot,
    HumanApprovalEvidence,
    MemoryProvenance,
    MemorySnapshotRecord,
    MemorySnapshotType,
    MemorySourceType,
    MemoryStateTransition,
    MemoryStatus,
    MemoryType,
    VerificationEvidenceBinding,
)
from embedded_copilot.engineering_memory.read_projection import (
    VerifiedMemoryReadProjection,
    project_verified_memory_read,
)
from embedded_copilot.engineering_memory.rules import build_candidate_record
from embedded_copilot.verification_agent import (
    VerificationStatus,
    VerificationSubjectType,
)

UTC_TIME = datetime(2026, 7, 30, 3, 0, tzinfo=UTC)
REQUESTED_AT = datetime(2026, 7, 30, 4, 0, tzinfo=UTC)
FINGERPRINT_A = "sha256:" + "a" * 64
FINGERPRINT_B = "sha256:" + "b" * 64


def _provenance(reference: str = "source-1") -> MemoryProvenance:
    return MemoryProvenance(
        source_type=MemorySourceType.VERIFICATION_RESULT,
        source_reference=reference,
        source_revision="revision-1",
        created_by="caller-1",
        observed_at=UTC_TIME,
    )


def _component(reference: str = "U1") -> ComponentMemory:
    return ComponentMemory(
        component_reference=reference,
        component_type="MCU",
        part_number="STM32F407VG",
        manufacturer="STMicroelectronics",
        quantity=1,
    )


def _candidate_record(
    *,
    record_id: str = "record-1",
    payload: ComponentMemory | EngineeringDecisionMemory | None = None,
    provenance: MemoryProvenance | None = None,
) -> EngineeringMemoryRecord:
    return build_candidate_record(
        request_id="create-1",
        operation_id="create-operation-1",
        project_id="project-1",
        memory_id="memory-1",
        record_id=record_id,
        payload=_component() if payload is None else payload,
        provenance=_provenance() if provenance is None else provenance,
        requested_at=UTC_TIME,
        aggregate_revision=1,
    )


def _verification_record(
    *,
    record_id: str = "record-1",
    payload: ComponentMemory | None = None,
    result_status: VerificationStatus = VerificationStatus.PASS,
    transition_reference: str = "verification-1",
    transitioned_at: datetime = UTC_TIME,
) -> EngineeringMemoryRecord:
    candidate = _candidate_record(record_id=record_id, payload=payload)
    target_status = (
        MemoryStatus.VERIFIED
        if result_status is VerificationStatus.PASS
        else MemoryStatus.REJECTED
    )
    binding = VerificationEvidenceBinding(
        verification_request_id="verification-1",
        subject_type=VerificationSubjectType.HARDWARE,
        result_status=result_status,
        request_fingerprint=FINGERPRINT_A,
        result_fingerprint=FINGERPRINT_B,
        requested_at=UTC_TIME,
        summary_reference="verification-result-1",
    )
    transition = MemoryStateTransition(
        from_status=MemoryStatus.CANDIDATE,
        to_status=target_status,
        request_id="verify-1",
        operation_id="verify-operation-1",
        evidence_type="VERIFICATION",
        evidence_reference=transition_reference,
        reason_code=(
            "VERIFICATION_PASSED"
            if target_status is MemoryStatus.VERIFIED
            else "VERIFICATION_FAILED"
        ),
        transitioned_at=transitioned_at,
    )
    return EngineeringMemoryRecord.model_validate(
        candidate.model_copy(
            update={
                "status": target_status,
                "record_revision": 1,
                "last_updated_aggregate_revision": 2,
                "last_transition_at": transitioned_at,
                "verification_bindings": (binding,),
                "state_history": candidate.state_history + (transition,),
            }
        )
    )


def _approval_record() -> EngineeringMemoryRecord:
    candidate = _candidate_record(
        payload=EngineeringDecisionMemory(
            decision_topic="rtos-choice",
            decision="Use FreeRTOS",
            rationale_summary="Existing platform support and deterministic scheduling",
        )
    )
    approval = HumanApprovalEvidence(
        approval_id="approval-1",
        record_id=candidate.record_id,
        record_revision=0,
        approved_by="reviewer-1",
        reason_code="PROJECT_ACCEPTED",
        approved_at=UTC_TIME,
    )
    transition = MemoryStateTransition(
        from_status=MemoryStatus.CANDIDATE,
        to_status=MemoryStatus.VERIFIED,
        request_id="approval-request-1",
        operation_id="approval-operation-1",
        evidence_type="HUMAN_APPROVAL",
        evidence_reference=approval.approval_id,
        reason_code=approval.reason_code,
        transitioned_at=UTC_TIME,
    )
    return EngineeringMemoryRecord.model_validate(
        candidate.model_copy(
            update={
                "status": MemoryStatus.VERIFIED,
                "record_revision": 1,
                "last_updated_aggregate_revision": 2,
                "last_transition_at": UTC_TIME,
                "approval_binding": approval,
                "state_history": candidate.state_history + (transition,),
            }
        )
    )


def _terminal_record(status: MemoryStatus) -> EngineeringMemoryRecord:
    verified = _verification_record()
    transition = MemoryStateTransition(
        from_status=MemoryStatus.VERIFIED,
        to_status=status,
        request_id="terminal-request-1",
        operation_id="terminal-operation-1",
        evidence_type=(
            "REVOCATION" if status is MemoryStatus.REVOKED else "VERIFICATION"
        ),
        evidence_reference="terminal-reference-1",
        reason_code="NO_LONGER_ACTIVE",
        transitioned_at=UTC_TIME,
    )
    return EngineeringMemoryRecord.model_validate(
        verified.model_copy(
            update={
                "status": status,
                "record_revision": 2,
                "last_updated_aggregate_revision": 3,
                "last_transition_at": UTC_TIME,
                "state_history": verified.state_history + (transition,),
            }
        )
    )


def _snapshot_record(
    record: EngineeringMemoryRecord,
    **changes: object,
) -> MemorySnapshotRecord:
    values: dict[str, object] = {
        "record_id": record.record_id,
        "memory_type": record.memory_type,
        "logical_key": record.logical_key,
        "payload": record.payload,
        "provenance": record.provenance,
        "status": record.status,
        "record_revision": record.record_revision,
        "supersedes_record_id": record.supersedes_record_id,
    }
    values.update(changes)
    return MemorySnapshotRecord(**values)


def _snapshot(
    *records: MemorySnapshotRecord,
    aggregate_revision: int = 2,
    project_id: str = "project-1",
) -> EngineeringMemorySnapshot:
    by_type = {memory_type: [] for memory_type in MemoryType}
    for record in records:
        by_type[record.memory_type].append(record)
    board_records = by_type[MemoryType.BOARD_PROFILE]
    return EngineeringMemorySnapshot(
        request_id="snapshot-1",
        snapshot_type=MemorySnapshotType.VERIFIED,
        project_id=project_id,
        memory_id="memory-1",
        aggregate_revision=aggregate_revision,
        board_profile=None if not board_records else board_records[0],
        components=tuple(by_type[MemoryType.COMPONENT]),
        pin_bindings=tuple(by_type[MemoryType.PIN_BINDING]),
        interface_bindings=tuple(by_type[MemoryType.INTERFACE_BINDING]),
        power_constraints=tuple(by_type[MemoryType.POWER_CONSTRAINT]),
        engineering_decisions=tuple(by_type[MemoryType.ENGINEERING_DECISION]),
        known_issues=tuple(by_type[MemoryType.KNOWN_ISSUE]),
        verification_records=tuple(by_type[MemoryType.VERIFICATION_HISTORY]),
        snapshot_fingerprint=FINGERPRINT_A,
    )


def _history_page(
    *records: EngineeringMemoryRecord,
    aggregate_revision: int = 2,
    project_id: str = "project-1",
    next_cursor: str | None = None,
) -> EngineeringMemoryHistoryPage:
    return EngineeringMemoryHistoryPage(
        request_id="history-1",
        project_id=project_id,
        memory_id="memory-1",
        aggregate_revision=aggregate_revision,
        records=records,
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


def _project(
    record: EngineeringMemoryRecord,
    *,
    snapshot_record: MemorySnapshotRecord | None = None,
    history_records: tuple[EngineeringMemoryRecord, ...] | None = None,
    requested_at: datetime = REQUESTED_AT,
) -> tuple[VerifiedMemoryReadProjection, ...]:
    selected = _snapshot_record(record) if snapshot_record is None else snapshot_record
    history = (record,) if history_records is None else history_records
    return project_verified_memory_read(
        snapshot=_snapshot(selected),
        history_pages=(_history_page(*history),),
        requested_at=requested_at,
    )


def test_verified_record_projects_safe_verification_metadata() -> None:
    projection = _project(_verification_record())
    assert projection == (
        VerifiedMemoryReadProjection(
            record_id="record-1",
            logical_key="component:U1",
            memory_type=MemoryType.COMPONENT,
            trust_basis=MemoryTrustBasis.VERIFICATION,
            verification_subject=VerificationSubjectType.HARDWARE,
            confidence=1.0,
            last_transition_at=UTC_TIME,
        ),
    )


@pytest.mark.parametrize(
    "status",
    (
        MemoryStatus.CANDIDATE,
        MemoryStatus.REJECTED,
        MemoryStatus.REVOKED,
        MemoryStatus.SUPERSEDED,
    ),
)
def test_non_verified_records_are_rejected(status: MemoryStatus) -> None:
    if status is MemoryStatus.CANDIDATE:
        record = _candidate_record()
    elif status is MemoryStatus.REJECTED:
        record = _verification_record(result_status=VerificationStatus.FAIL)
    else:
        record = _terminal_record(status)
    with pytest.raises(MemoryRetrievalUnavailable):
        _project(record)


def test_human_approval_projects_fixed_read_side_confidence() -> None:
    projection = _project(_approval_record())[0]
    assert projection.trust_basis is MemoryTrustBasis.HUMAN_APPROVAL
    assert projection.verification_subject is None
    assert projection.confidence == 0.5


def test_projection_contract_is_strict_frozen_and_content_bounded() -> None:
    value = _project(_verification_record())[0]
    assert tuple(VerifiedMemoryReadProjection.model_fields) == (
        "record_id",
        "logical_key",
        "memory_type",
        "trust_basis",
        "verification_subject",
        "confidence",
        "last_transition_at",
    )
    assert VerifiedMemoryReadProjection.model_config == {
        "frozen": True,
        "strict": True,
        "extra": "forbid",
        "hide_input_in_errors": True,
        "revalidate_instances": "always",
    }
    with pytest.raises(ValidationError):
        value.confidence = 0.5
    with pytest.raises(ValidationError):
        VerifiedMemoryReadProjection(
            **(value.model_dump() | {"confidence": True})
        )
    with pytest.raises(ValidationError):
        VerifiedMemoryReadProjection(**value.model_dump(), finding="forbidden")
    assert {
        "payload",
        "finding",
        "approval",
        "approval_body",
        "history",
        "state_history",
        "verification_result",
        "request_fingerprint",
        "result_fingerprint",
    }.isdisjoint(value.model_dump())


def test_projection_timestamp_is_utc_normalized() -> None:
    plus_eight = datetime(2026, 7, 30, 11, 0, tzinfo=timezone(timedelta(hours=8)))
    value = VerifiedMemoryReadProjection(
        record_id="record-1",
        logical_key="component:U1",
        memory_type=MemoryType.COMPONENT,
        trust_basis=MemoryTrustBasis.VERIFICATION,
        verification_subject=VerificationSubjectType.HARDWARE,
        confidence=1.0,
        last_transition_at=plus_eight,
    )
    assert value.last_transition_at == UTC_TIME
    assert value.last_transition_at.tzinfo is UTC
    with pytest.raises(ValidationError, match="timezone aware"):
        VerifiedMemoryReadProjection(
            **value.model_dump()
            | {"last_transition_at": datetime(2026, 7, 30, 3, 0)}  # noqa: DTZ001
        )
    with pytest.raises(MemoryRetrievalUnavailable):
        _project(
            _verification_record(),
            requested_at=datetime(2026, 7, 30, 4, 0),  # noqa: DTZ001
        )


def test_projection_serialization_and_order_are_deterministic() -> None:
    second = _verification_record(record_id="record-2", payload=_component("U2"))
    first = _verification_record(record_id="record-1", payload=_component("U1"))
    snapshot = _snapshot(_snapshot_record(second), _snapshot_record(first))
    history = _history_page(first, second)
    projected = project_verified_memory_read(
        snapshot=snapshot,
        history_pages=(history,),
        requested_at=REQUESTED_AT,
    )
    repeated = project_verified_memory_read(
        snapshot=EngineeringMemorySnapshot.model_validate(snapshot.model_dump()),
        history_pages=(
            EngineeringMemoryHistoryPage.model_validate(history.model_dump()),
        ),
        requested_at=REQUESTED_AT,
    )
    assert tuple(item.record_id for item in projected) == ("record-2", "record-1")
    assert tuple(item.model_dump_json() for item in projected) == tuple(
        item.model_dump_json() for item in repeated
    )


@pytest.mark.parametrize(
    "case",
    (
        "missing_history",
        "duplicate_history",
        "aggregate_revision",
        "project_identity",
        "payload",
        "provenance",
        "record_revision",
        "logical_key",
        "supersedes_record_id",
    ),
)
def test_snapshot_history_inconsistencies_fail_closed(case: str) -> None:
    record = _verification_record()
    snapshot_record = _snapshot_record(record)
    snapshot = _snapshot(snapshot_record)
    history_records = (record,)
    history = _history_page(record)

    if case == "missing_history":
        history = _history_page()
    elif case == "duplicate_history":
        history = _history_page(record, record)
    elif case == "aggregate_revision":
        history = _history_page(record, aggregate_revision=3)
    elif case == "project_identity":
        history = _history_page(record, project_id="project-2")
    elif case == "payload":
        snapshot_record = _snapshot_record(record, payload=_component("U2"))
        snapshot = _snapshot(snapshot_record)
    elif case == "provenance":
        snapshot_record = _snapshot_record(record, provenance=_provenance("source-2"))
        snapshot = _snapshot(snapshot_record)
    elif case == "record_revision":
        snapshot_record = _snapshot_record(record, record_revision=0)
        snapshot = _snapshot(snapshot_record)
    elif case == "logical_key":
        snapshot_record = _snapshot_record(record, logical_key="component:U2")
        snapshot = _snapshot(snapshot_record)
    elif case == "supersedes_record_id":
        snapshot_record = _snapshot_record(
            record,
            supersedes_record_id="record-previous",
        )
        snapshot = _snapshot(snapshot_record)

    with pytest.raises(MemoryRetrievalUnavailable):
        project_verified_memory_read(
            snapshot=snapshot,
            history_pages=(history,),
            requested_at=REQUESTED_AT,
        )
    assert history_records == (record,)


@pytest.mark.parametrize(
    "case",
    ("future_transition", "non_pass_binding", "binding_reference", "approval_reference"),
)
def test_invalid_final_trust_binding_is_rejected(case: str) -> None:
    if case == "future_transition":
        record = _verification_record(transitioned_at=REQUESTED_AT + timedelta(seconds=1))
    elif case == "non_pass_binding":
        record = _verification_record()
        binding = record.verification_bindings[-1].model_copy(
            update={"result_status": VerificationStatus.REVIEW_REQUIRED}
        )
        record = EngineeringMemoryRecord.model_validate(
            record.model_copy(update={"verification_bindings": (binding,)})
        )
    elif case == "binding_reference":
        record = _verification_record(transition_reference="verification-2")
    else:
        record = _approval_record()
        transition = record.state_history[-1].model_copy(
            update={"evidence_reference": "approval-2"}
        )
        record = EngineeringMemoryRecord.model_validate(
            record.model_copy(
                update={
                    "state_history": record.state_history[:-1] + (transition,),
                }
            )
        )
    with pytest.raises(MemoryRetrievalUnavailable):
        _project(record)


def test_inputs_are_not_mutated_during_projection() -> None:
    record = _verification_record()
    snapshot = _snapshot(_snapshot_record(record))
    history = _history_page(record)
    snapshot_before = snapshot.model_dump_json()
    history_before = history.model_dump_json()
    project_verified_memory_read(
        snapshot=snapshot,
        history_pages=(history,),
        requested_at=REQUESTED_AT,
    )
    assert snapshot.model_dump_json() == snapshot_before
    assert history.model_dump_json() == history_before
