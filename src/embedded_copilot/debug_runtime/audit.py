from __future__ import annotations

from datetime import datetime

from embedded_copilot.debug_runtime.exceptions import DebugAuditUnavailable
from embedded_copilot.debug_runtime.models import (
    DebugAuditEvent,
    DebugAuditEventType,
    DebugSourceType,
)
from embedded_copilot.debug_runtime.ports import DebugAuditSink


def emit_audit(
    sink: DebugAuditSink,
    *,
    event_type: DebugAuditEventType,
    target_id: str,
    source_type: DebugSourceType,
    timestamp: datetime,
) -> None:
    try:
        sink.record(
            DebugAuditEvent(
                event_type=event_type,
                target_id=target_id,
                source_type=source_type,
                timestamp=timestamp,
            )
        )
    except Exception:
        raise DebugAuditUnavailable from None
