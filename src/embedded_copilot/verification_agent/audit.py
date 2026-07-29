from __future__ import annotations

from datetime import datetime

from embedded_copilot.verification_agent.exceptions import (
    VerificationAuditUnavailable,
)
from embedded_copilot.verification_agent.models import (
    VerificationAuditEvent,
    VerificationAuditEventType,
    VerificationSubjectType,
)
from embedded_copilot.verification_agent.ports import VerificationAuditSink


def emit_audit(
    sink: VerificationAuditSink,
    *,
    event_type: VerificationAuditEventType,
    request_id: str,
    subject_type: VerificationSubjectType,
    timestamp: datetime,
) -> None:
    try:
        sink.record(
            VerificationAuditEvent(
                event_type=event_type,
                request_id=request_id,
                subject_type=subject_type,
                timestamp=timestamp,
            )
        )
    except Exception:
        raise VerificationAuditUnavailable from None
