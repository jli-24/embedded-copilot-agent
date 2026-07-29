from __future__ import annotations

import inspect

import pytest

import embedded_copilot.engineering_memory as memory


class _Store:
    def create_candidate(self, request, *, request_fingerprint):
        raise NotImplementedError

    def create_replacement_candidate(self, request, *, request_fingerprint):
        raise NotImplementedError

    def apply_verification(self, request, *, request_fingerprint):
        raise NotImplementedError

    def apply_human_approval(self, request, *, request_fingerprint):
        raise NotImplementedError

    def revoke_record(self, request, *, request_fingerprint):
        raise NotImplementedError

    def get_verified_snapshot(self, request):
        raise NotImplementedError

    def get_candidate_snapshot(self, request):
        raise NotImplementedError

    def get_history(self, request):
        raise NotImplementedError


class _Permission:
    def authorize(self, request):
        raise NotImplementedError


class _Audit:
    def record(self, event):
        return None


def _public_methods(value: type[object]) -> set[str]:
    return {
        name
        for name, member in value.__dict__.items()
        if callable(member) and not name.startswith("_")
    }


def test_facade_and_protocols_are_narrow() -> None:
    facade = memory.create_engineering_memory(
        store=_Store(), permission_port=_Permission(), audit_sink=_Audit()
    )
    assert _public_methods(type(facade)) == {"memory_port"}
    assert _public_methods(memory.EngineeringMemoryPort) == {"execute"}
    assert _public_methods(memory.MemoryPermissionPort) == {"authorize"}
    assert _public_methods(memory.MemoryAuditSink) == {"record"}
    assert _public_methods(memory.EngineeringMemoryStorePort) == {
        "create_candidate",
        "create_replacement_candidate",
        "apply_verification",
        "apply_human_approval",
        "revoke_record",
        "get_verified_snapshot",
        "get_candidate_snapshot",
        "get_history",
    }
    assert isinstance(facade.memory_port(), memory.EngineeringMemoryPort)


def test_factory_rejects_invalid_or_async_dependencies() -> None:
    with pytest.raises(TypeError, match="store"):
        memory.create_engineering_memory(
            store=object(), permission_port=_Permission(), audit_sink=_Audit()
        )

    class _AsyncPermission:
        async def authorize(self, request):
            raise NotImplementedError

    assert inspect.iscoroutinefunction(_AsyncPermission.authorize)
    with pytest.raises(TypeError, match="permission"):
        memory.create_engineering_memory(
            store=_Store(), permission_port=_AsyncPermission(), audit_sink=_Audit()
        )

    class _NonCallableStore:
        create_candidate = 1
        create_replacement_candidate = 1
        apply_verification = 1
        apply_human_approval = 1
        revoke_record = 1
        get_verified_snapshot = 1
        get_candidate_snapshot = 1
        get_history = 1

    with pytest.raises(TypeError, match="store"):
        memory.create_engineering_memory(
            store=_NonCallableStore(),
            permission_port=_Permission(),
            audit_sink=_Audit(),
        )


def test_factory_has_no_default_dependencies() -> None:
    signature = inspect.signature(memory.create_engineering_memory)
    assert tuple(signature.parameters) == ("store", "permission_port", "audit_sink")
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )


def test_package_exports_only_approved_public_contracts() -> None:
    for leaked in (
        "EngineeringMemoryService",
        "InMemoryEngineeringMemoryStore",
        "Aggregate",
        "OperationReceipt",
        "canonical_fingerprint",
        "logical_key_for",
        "emit_audit",
        "RLock",
    ):
        assert leaked not in memory.__all__
        assert not hasattr(memory, leaked)
    assert {
        "EngineeringMemory",
        "EngineeringMemoryPort",
        "EngineeringMemoryStorePort",
        "MemoryPermissionPort",
        "MemoryAuditSink",
        "create_engineering_memory",
    } <= set(memory.__all__)
