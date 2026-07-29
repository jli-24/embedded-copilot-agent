from __future__ import annotations

from .exceptions import MemoryAuditUnavailable
from .models import MemoryAuditEvent, MemoryAuditEventType


def build_audit_event(request, event_type: MemoryAuditEventType) -> MemoryAuditEvent:
    operation_id = getattr(request, "operation_id", None)
    if operation_id is None:
        event_key = f"memory-audit:{request.request_id}:{event_type.value}"
    else:
        event_key = (
            f"memory-audit:{request.request_id}:{operation_id}:{event_type.value}"
        )
    return MemoryAuditEvent(
        event_key=event_key,
        event_type=event_type,
        request_id=request.request_id,
        operation_id=operation_id,
        project_id=request.project_id,
        memory_id=request.memory_id,
        record_id=getattr(request, "record_id", None),
        command_type=request.command_type,
        timestamp=request.requested_at,
    )


def record_audit(sink, event: MemoryAuditEvent) -> None:
    try:
        sink.record(MemoryAuditEvent.model_validate(event))
    except Exception as error:
        raise MemoryAuditUnavailable() from error
