import pytest

from embedded_copilot.engineering_memory import (
    MemoryAction,
    MemoryPermissionDecision,
    MemoryPermissionDenied,
    MemoryPermissionStatus,
    create_engineering_memory,
)
from embedded_copilot.engineering_memory.stores.in_memory import (
    InMemoryEngineeringMemoryStore,
)

from .test_mutations import _create


class _Permission:
    def __init__(self, decision=MemoryPermissionStatus.ALLOWED):
        self.decision = decision
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        return MemoryPermissionDecision(
            **request.model_dump(),
            decision=self.decision,
            reason_code=(
                "AUTHORIZED"
                if self.decision is MemoryPermissionStatus.ALLOWED
                else "POLICY_DENIED"
            ),
        )


class _Audit:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


def test_permission_receives_only_nine_bound_fields() -> None:
    permission = _Permission()
    port = create_engineering_memory(
        store=InMemoryEngineeringMemoryStore(),
        permission_port=permission,
        audit_sink=_Audit(),
    ).memory_port()
    port.execute(_create())
    authorization = permission.requests[0]
    assert tuple(type(authorization).model_fields) == (
        "request_id",
        "operation_id",
        "project_id",
        "memory_id",
        "caller",
        "command_type",
        "action",
        "request_fingerprint",
        "requested_at",
    )
    assert authorization.action is MemoryAction.CREATE_MEMORY_CANDIDATE
    serialized = authorization.model_dump_json().casefold()
    assert all(word not in serialized for word in ("payload", "provenance", "finding"))


def test_permission_deny_is_fail_closed() -> None:
    permission = _Permission(MemoryPermissionStatus.DENIED)
    audit = _Audit()
    port = create_engineering_memory(
        store=InMemoryEngineeringMemoryStore(),
        permission_port=permission,
        audit_sink=audit,
    ).memory_port()
    with pytest.raises(MemoryPermissionDenied):
        port.execute(_create())
    assert tuple(event.event_type.value for event in audit.events) == (
        "MEMORY_REQUESTED",
        "MEMORY_REJECTED",
    )


@pytest.mark.parametrize("mode", ("mismatch", "malformed", "exception"))
def test_permission_adapter_failures_are_clean_and_record_failed(mode) -> None:
    class _InvalidPermission:
        def authorize(self, request):
            if mode == "exception":
                raise RuntimeError("private permission path")
            if mode == "malformed":
                return object()
            return MemoryPermissionDecision(
                **request.model_dump() | {"request_id": "different-request"},
                decision=MemoryPermissionStatus.ALLOWED,
                reason_code="AUTHORIZED",
            )

    audit = _Audit()
    port = create_engineering_memory(
        store=InMemoryEngineeringMemoryStore(),
        permission_port=_InvalidPermission(),
        audit_sink=audit,
    ).memory_port()
    with pytest.raises(MemoryPermissionDenied) as captured:
        port.execute(_create())
    assert str(captured.value) == "MEMORY_PERMISSION_DENIED"
    assert captured.value.__cause__ is not None
    assert tuple(event.event_type.value for event in audit.events) == (
        "MEMORY_REQUESTED",
        "MEMORY_FAILED",
    )
