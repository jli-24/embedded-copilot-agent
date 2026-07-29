from __future__ import annotations

import inspect

from .facade import EngineeringMemory
from .ports import EngineeringMemoryStorePort, MemoryAuditSink, MemoryPermissionPort
from .service import _EngineeringMemoryPort


def _require_sync_protocol(value: object, protocol: type[object], name: str) -> None:
    if not isinstance(value, protocol):
        raise TypeError(f"{name} does not satisfy its protocol")
    for method_name in protocol.__dict__:
        if method_name.startswith("_"):
            continue
        method = getattr(value, method_name, None)
        if (
            not callable(method)
            or inspect.iscoroutinefunction(method)
            or inspect.iscoroutinefunction(type(method).__call__)
        ):
            raise TypeError(f"{name} must use synchronous methods")


def create_engineering_memory(
    *,
    store: EngineeringMemoryStorePort,
    permission_port: MemoryPermissionPort,
    audit_sink: MemoryAuditSink,
) -> EngineeringMemory:
    _require_sync_protocol(store, EngineeringMemoryStorePort, "store")
    _require_sync_protocol(permission_port, MemoryPermissionPort, "permission_port")
    _require_sync_protocol(audit_sink, MemoryAuditSink, "audit_sink")
    return EngineeringMemory._compose(
        _EngineeringMemoryPort(
            store=store, permission_port=permission_port, audit_sink=audit_sink
        )
    )
