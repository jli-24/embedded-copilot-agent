from datetime import datetime, timezone

import pytest

from embedded_copilot.engineering_memory import (
    BoardProfileMemory,
    CreateCandidateRequest,
    GetCandidateSnapshotRequest,
    MemoryOperationConflict,
    PinBindingMemory,
    MemoryProvenance,
    MemoryRevisionConflict,
    MemorySourceType,
    MemoryStateTransitionRejected,
)
from embedded_copilot.engineering_memory.stores.in_memory import (
    InMemoryEngineeringMemoryStore,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
FP = "sha256:" + "a" * 64


def _create(**changes: object) -> CreateCandidateRequest:
    values = {
        "request_id": "req-1",
        "operation_id": "op-1",
        "project_id": "project-1",
        "memory_id": "memory-1",
        "caller": "caller-1",
        "requested_at": NOW,
        "expected_revision": 0,
        "record_id": "record-1",
        "payload": BoardProfileMemory(
            board_id="board-1",
            board_name="Board One",
            mcu_family="STM32",
            mcu_model="STM32F407",
            architecture="ARM Cortex-M4",
        ),
        "provenance": MemoryProvenance(
            source_type=MemorySourceType.USER_INPUT,
            source_reference="source-1",
            source_revision="revision-1",
            created_by="caller-1",
            observed_at=NOW,
        ),
    }
    values.update(changes)
    return CreateCandidateRequest(**values)


def _read() -> GetCandidateSnapshotRequest:
    return GetCandidateSnapshotRequest(
        request_id="read-1",
        project_id="project-1",
        memory_id="memory-1",
        caller="caller-1",
        requested_at=NOW,
    )


def test_create_candidate_and_receipt_replay_precedes_revision() -> None:
    store = InMemoryEngineeringMemoryStore()
    request = _create()
    first = store.create_candidate(request, request_fingerprint=FP)
    replay = store.create_candidate(request, request_fingerprint=FP)
    assert replay == first
    assert first.aggregate_revision == 1
    assert first.affected_records[0].record_revision == 0
    assert store.get_candidate_snapshot(_read()).aggregate_revision == 1


def test_operation_conflict_revision_and_slot_conflicts_are_clean() -> None:
    store = InMemoryEngineeringMemoryStore()
    store.create_candidate(_create(), request_fingerprint=FP)
    with pytest.raises(MemoryOperationConflict):
        store.create_candidate(
            _create(record_id="record-2"), request_fingerprint="sha256:" + "b" * 64
        )
    with pytest.raises(MemoryRevisionConflict):
        store.create_candidate(
            _create(operation_id="op-2", record_id="record-2"),
            request_fingerprint="sha256:" + "c" * 64,
        )
    with pytest.raises(MemoryStateTransitionRejected):
        store.create_candidate(
            _create(operation_id="op-3", expected_revision=1, record_id="record-2"),
            request_fingerprint="sha256:" + "d" * 64,
        )


def test_maximum_length_segments_form_valid_unambiguous_derived_keys() -> None:
    store = InMemoryEngineeringMemoryStore()
    segment = "a" * 40
    request = _create(
        request_id="r" * 40,
        operation_id="o" * 40,
        project_id="p" * 40,
        memory_id="m" * 40,
        caller="c" * 40,
        record_id="d" * 40,
        payload=PinBindingMemory(
            target_id=segment,
            pin_id="b" * 40,
            function="function-1",
            component_reference="component-1",
            interface_reference="interface-1",
        ),
    )
    result = store.create_candidate(request, request_fingerprint="sha256:" + "e" * 64)
    assert result.aggregate_revision == 1
