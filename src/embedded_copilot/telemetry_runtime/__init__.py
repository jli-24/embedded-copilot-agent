"""Framework-independent telemetry intelligence runtime."""

from embedded_copilot.telemetry_runtime.exceptions import (
    TelemetryAuditUnavailable,
    TelemetryDataRejected,
    TelemetryObservationTimeout,
    TelemetrySourceUnavailable,
)
from embedded_copilot.telemetry_runtime.factory import create_telemetry_runtime
from embedded_copilot.telemetry_runtime.models import (
    DebugTelemetryContext,
    TelemetryAnalysisRequest,
    TelemetryAnalysisResult,
    TelemetryAnomalyCandidate,
    TelemetryAnomalyDirection,
    TelemetryAuditEvent,
    TelemetryAuditEventType,
    TelemetryMetric,
    TelemetryRequest,
    TelemetrySample,
    TelemetrySeriesPoint,
    TelemetrySeriesRequest,
    TelemetrySeriesSnapshot,
    TelemetrySourceType,
    TelemetryStatistics,
    TelemetryTrend,
    TelemetryUnit,
)
from embedded_copilot.telemetry_runtime.ports import (
    TelemetryAuditSink,
    TelemetryPort,
    TelemetrySourcePort,
)
from embedded_copilot.telemetry_runtime.runtime import TelemetryRuntime

__all__ = (
    "DebugTelemetryContext",
    "TelemetryAnalysisRequest",
    "TelemetryAnalysisResult",
    "TelemetryAnomalyCandidate",
    "TelemetryAnomalyDirection",
    "TelemetryAuditEvent",
    "TelemetryAuditEventType",
    "TelemetryAuditSink",
    "TelemetryAuditUnavailable",
    "TelemetryDataRejected",
    "TelemetryMetric",
    "TelemetryObservationTimeout",
    "TelemetryPort",
    "TelemetryRequest",
    "TelemetryRuntime",
    "TelemetrySample",
    "TelemetrySeriesPoint",
    "TelemetrySeriesRequest",
    "TelemetrySeriesSnapshot",
    "TelemetrySourcePort",
    "TelemetrySourceType",
    "TelemetrySourceUnavailable",
    "TelemetryStatistics",
    "TelemetryTrend",
    "TelemetryUnit",
    "create_telemetry_runtime",
)
