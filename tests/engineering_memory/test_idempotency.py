import pytest

from embedded_copilot.engineering_memory import (
    GetCandidateSnapshotRequest,
    MemoryAuditUnavailable,
    MemoryPermissionDecision,
    MemoryPermissionStatus,
    create_engineering_memory,
)
from embedded_copilot.engineering_memory.stores.in_memory import (
    InMemoryEngineeringMemoryStore,
)

from .test_mutations import NOW, _create


class _Permission:
    def authorize(self, request):
        return MemoryPermissionDecision(
            **request.model_dump(),
            decision=MemoryPermissionStatus.ALLOWED,
            reason_code="AUTHORIZED",
        )


class _TerminalFailsOnceAudit:
    def __init__(self):
        self.attempted_terminal_keys = []
        self.failed = False
        self.events = {}

    def record(self, event):
        if event.event_type.value == "MEMORY_COMPLETED":
            self.attempted_terminal_keys.append(event.event_key)
            if not self.failed:
                self.failed = True
                self.events[event.event_key] = event
                raise RuntimeError("terminal sink unavailable")
        existing = self.events.get(event.event_key)
        if existing is not None and existing != event:
            raise RuntimeError("audit key conflict")
        self.events[event.event_key] = event


def test_terminal_audit_failure_replay_does_not_repeat_mutation() -> None:
    store = InMemoryEngineeringMemoryStore()
    audit = _TerminalFailsOnceAudit()
    port = create_engineering_memory(
        store=store, permission_port=_Permission(), audit_sink=audit
    ).memory_port()
    request = _create()
    with pytest.raises(MemoryAuditUnavailable):
        port.execute(request)
    result = port.execute(request)
    assert result.aggregate_revision == 1
    snapshot = store.get_candidate_snapshot(
        GetCandidateSnapshotRequest(
            request_id="read-1",
            project_id="project-1",
            memory_id="memory-1",
            caller="caller-1",
            requested_at=NOW,
        )
    )
    assert snapshot.aggregate_revision == 1
    assert audit.attempted_terminal_keys == [
        "memory-audit:req-1:op-1:MEMORY_COMPLETED",
        "memory-audit:req-1:op-1:MEMORY_COMPLETED",
    ]
