from __future__ import annotations

from datetime import datetime

from embedded_copilot.tool_runtime.exceptions import ToolAuditUnavailable
from embedded_copilot.tool_runtime.models import ToolAuditEvent, ToolAuditEventType
from embedded_copilot.tool_runtime.ports import ToolAuditSink


def emit_audit(
    sink: ToolAuditSink,
    *,
    event_type: ToolAuditEventType,
    tool_name: str,
    request_id: str,
    caller: str,
    timestamp: datetime,
) -> None:
    try:
        sink.record(
            ToolAuditEvent(
                event_type=event_type,
                tool_name=tool_name,
                request_id=request_id,
                caller=caller,
                timestamp=timestamp,
            )
        )
    except Exception:
        raise ToolAuditUnavailable from None
