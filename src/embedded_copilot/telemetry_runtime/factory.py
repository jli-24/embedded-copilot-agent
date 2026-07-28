from __future__ import annotations

from embedded_copilot.telemetry_runtime.models import TelemetrySourceType
from embedded_copilot.telemetry_runtime.ports import (
    TelemetryAuditSink,
    TelemetrySourcePort,
)
from embedded_copilot.telemetry_runtime.runtime import (
    TelemetryRuntime,
    _SourceAdapter,
    _TelemetryPort,
)


def create_telemetry_runtime(
    *,
    sources: tuple[TelemetrySourcePort, ...],
    audit_sink: TelemetryAuditSink,
) -> TelemetryRuntime:
    if not isinstance(sources, tuple):
        raise TypeError("sources must be a tuple")
    if not sources:
        raise ValueError("sources must not be empty")
    if not isinstance(audit_sink, TelemetryAuditSink):
        raise TypeError("audit sink is invalid")
    adapters: list[_SourceAdapter] = []
    source_types: list[TelemetrySourceType] = []
    for source in sources:
        try:
            source_is_valid = isinstance(source, TelemetrySourcePort)
        except Exception:
            raise TypeError("telemetry source type is invalid") from None
        if not source_is_valid:
            raise TypeError("telemetry source is invalid")
        try:
            source_type = source.source_type
        except Exception:
            raise TypeError("telemetry source type is invalid") from None
        if not isinstance(source_type, TelemetrySourceType):
            raise TypeError("telemetry source type is invalid")
        source_types.append(source_type)
        adapters.append(_SourceAdapter(source_type=source_type, source=source))
    if len(source_types) != len(set(source_types)):
        raise ValueError("source types must be unique")
    return TelemetryRuntime._compose(_TelemetryPort(tuple(adapters), audit_sink))
