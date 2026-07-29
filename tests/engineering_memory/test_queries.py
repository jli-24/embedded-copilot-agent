from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_memory import (
    ComponentMemory,
    CreateCandidateRequest,
    GetCandidateSnapshotRequest,
    GetHistoryRequest,
    GetVerifiedSnapshotRequest,
    MemoryProvenance,
    MemoryRevisionConflict,
    MemorySourceType,
)
from embedded_copilot.engineering_memory.stores.in_memory import (
    InMemoryEngineeringMemoryStore,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def _create(number: int, revision: int) -> CreateCandidateRequest:
    return CreateCandidateRequest(
        request_id=f"req-{number}",
        operation_id=f"op-{number}",
        project_id="project-1",
        memory_id="memory-1",
        caller="caller-1",
        requested_at=NOW,
        expected_revision=revision,
        record_id=f"record-{number}",
        payload=ComponentMemory(
            component_reference=f"U{number}",
            component_type="Sensor",
            part_number=f"PN-{number}",
            manufacturer="Vendor",
            quantity=1,
        ),
        provenance=MemoryProvenance(
            source_type=MemorySourceType.USER_INPUT,
            source_reference=f"source-{number}",
            source_revision="revision-1",
            created_by="caller-1",
            observed_at=NOW,
        ),
    )


def _read(cls, **changes):
    values = {
        "request_id": "read-1",
        "project_id": "project-1",
        "memory_id": "memory-1",
        "caller": "caller-1",
        "requested_at": NOW,
    }
    values.update(changes)
    return cls(**values)


def test_snapshots_are_isolated_sorted_and_fingerprinted() -> None:
    store = InMemoryEngineeringMemoryStore()
    store.create_candidate(_create(2, 0), request_fingerprint="sha256:" + "a" * 64)
    store.create_candidate(_create(1, 1), request_fingerprint="sha256:" + "b" * 64)
    candidate = store.get_candidate_snapshot(_read(GetCandidateSnapshotRequest))
    verified = store.get_verified_snapshot(_read(GetVerifiedSnapshotRequest))
    assert tuple(record.logical_key for record in candidate.records) == (
        "component:U1",
        "component:U2",
    )
    assert verified.records == ()
    assert candidate.snapshot_fingerprint.startswith("sha256:")
    assert store.get_candidate_snapshot(_read(GetCandidateSnapshotRequest)) == candidate


def test_history_cursor_is_revision_bound() -> None:
    store = InMemoryEngineeringMemoryStore()
    store.create_candidate(_create(1, 0), request_fingerprint="sha256:" + "a" * 64)
    store.create_candidate(_create(2, 1), request_fingerprint="sha256:" + "b" * 64)
    first = store.get_history(_read(GetHistoryRequest, limit=1))
    assert first.next_cursor == "revision:2:offset:1"
    second = store.get_history(
        _read(GetHistoryRequest, limit=1, cursor=first.next_cursor)
    )
    assert tuple(record.record_id for record in second.records) == ("record-2",)
    store.create_candidate(_create(3, 2), request_fingerprint="sha256:" + "c" * 64)
    with pytest.raises(MemoryRevisionConflict):
        store.get_history(_read(GetHistoryRequest, limit=1, cursor=first.next_cursor))
