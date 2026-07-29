import pytest

from embedded_copilot.engineering_memory import (
    GetCandidateSnapshotRequest,
    GetHistoryRequest,
    MemoryAuditUnavailable,
    MemoryPermissionDecision,
    MemoryPermissionStatus,
    MemoryRevisionConflict,
    MemoryStoreUnavailable,
    create_engineering_memory,
)
from embedded_copilot.engineering_memory.stores.in_memory import (
    InMemoryEngineeringMemoryStore,
)

from .test_mutations import NOW, _create


class _Permission:
    def __init__(self):
        self.calls = 0

    def authorize(self, request):
        self.calls += 1
        return MemoryPermissionDecision(
            **request.model_dump(),
            decision=MemoryPermissionStatus.ALLOWED,
            reason_code="AUTHORIZED",
        )


class _Audit:
    def __init__(self, fail_first=False):
        self.events = []
        self.fail_first = fail_first

    def record(self, event):
        if self.fail_first and not self.events:
            raise RuntimeError("private audit adapter failure")
        self.events.append(event)


def test_audit_is_content_free_ordered_and_uses_stable_keys() -> None:
    audit = _Audit()
    request = _create()
    port = create_engineering_memory(
        store=InMemoryEngineeringMemoryStore(),
        permission_port=_Permission(),
        audit_sink=audit,
    ).memory_port()
    port.execute(request)
    assert tuple(event.event_type.value for event in audit.events) == (
        "MEMORY_REQUESTED",
        "MEMORY_COMPLETED",
    )
    assert audit.events[0].event_key == ("memory-audit:req-1:op-1:MEMORY_REQUESTED")
    assert audit.events[1].event_key == ("memory-audit:req-1:op-1:MEMORY_COMPLETED")
    assert all(event.timestamp == request.requested_at for event in audit.events)
    serialized = "".join(event.model_dump_json() for event in audit.events).casefold()
    assert all(word not in serialized for word in ("payload", "source-1", "stm32"))


def test_requested_audit_failure_prevents_permission_and_store() -> None:
    permission = _Permission()
    store = InMemoryEngineeringMemoryStore()
    port = create_engineering_memory(
        store=store, permission_port=permission, audit_sink=_Audit(fail_first=True)
    ).memory_port()
    with pytest.raises(MemoryAuditUnavailable):
        port.execute(_create())
    assert permission.calls == 0


def test_query_terminal_audit_failure_returns_no_snapshot() -> None:
    class _TerminalAudit:
        def record(self, event):
            if event.event_type.value == "MEMORY_COMPLETED":
                raise RuntimeError("terminal unavailable")

    port = create_engineering_memory(
        store=InMemoryEngineeringMemoryStore(),
        permission_port=_Permission(),
        audit_sink=_TerminalAudit(),
    ).memory_port()
    with pytest.raises(MemoryAuditUnavailable):
        port.execute(
            GetCandidateSnapshotRequest(
                request_id="read-1",
                project_id="project-1",
                memory_id="memory-1",
                caller="caller-1",
                requested_at=NOW,
            )
        )


def test_store_result_binding_and_domain_errors_are_clean() -> None:
    class _StoreProxy:
        def __init__(self, mode):
            self.mode = mode
            self.delegate = InMemoryEngineeringMemoryStore()

        def __getattr__(self, name):
            return getattr(self.delegate, name)

        def create_candidate(self, request, *, request_fingerprint):
            if self.mode == "domain":
                error = MemoryRevisionConflict()
                error.args = ("private/path/payload",)
                raise error
            result = self.delegate.create_candidate(
                request, request_fingerprint=request_fingerprint
            )
            return result.model_copy(update={"request_id": "different-request"})

    for mode, expected, terminal in (
        ("binding", MemoryStoreUnavailable, "MEMORY_FAILED"),
        ("domain", MemoryRevisionConflict, "MEMORY_REJECTED"),
    ):
        audit = _Audit()
        port = create_engineering_memory(
            store=_StoreProxy(mode),
            permission_port=_Permission(),
            audit_sink=audit,
        ).memory_port()
        with pytest.raises(expected) as captured:
            port.execute(_create())
        assert "private" not in str(captured.value)
        assert audit.events[-1].event_type.value == terminal


def test_store_query_result_kind_must_match_authorized_command() -> None:
    class _WrongKindStore:
        def __init__(self):
            self.delegate = InMemoryEngineeringMemoryStore()

        def __getattr__(self, name):
            return getattr(self.delegate, name)

        def get_candidate_snapshot(self, request):
            return self.delegate.get_history(
                GetHistoryRequest(
                    request_id=request.request_id,
                    project_id=request.project_id,
                    memory_id=request.memory_id,
                    caller=request.caller,
                    requested_at=request.requested_at,
                )
            )

    port = create_engineering_memory(
        store=_WrongKindStore(),
        permission_port=_Permission(),
        audit_sink=_Audit(),
    ).memory_port()
    with pytest.raises(MemoryStoreUnavailable):
        port.execute(
            GetCandidateSnapshotRequest(
                request_id="read-1",
                project_id="project-1",
                memory_id="memory-1",
                caller="caller-1",
                requested_at=NOW,
            )
        )
