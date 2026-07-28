from __future__ import annotations

from datetime import datetime

from embedded_copilot.telemetry_runtime.exceptions import (
    TelemetryAuditUnavailable,
)
from embedded_copilot.telemetry_runtime.models import (
    TelemetryAuditEvent,
    TelemetryAuditEventType,
    TelemetrySourceType,
)
from embedded_copilot.telemetry_runtime.ports import TelemetryAuditSink


def emit_audit(
    sink: TelemetryAuditSink,
    *,
    event_type: TelemetryAuditEventType,
    target_id: str,
    source_type: TelemetrySourceType,
    timestamp: datetime,
) -> None:
    event = TelemetryAuditEvent(
        event_type=event_type,
        target_id=target_id,
        source_type=source_type,
        timestamp=timestamp,
    )
    try:
        sink.record(event)
    except Exception:
        raise TelemetryAuditUnavailable from None
