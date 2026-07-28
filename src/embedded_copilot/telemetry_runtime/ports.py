from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.telemetry_runtime.models import (
    TelemetryAnalysisRequest,
    TelemetryAnalysisResult,
    TelemetryAuditEvent,
    TelemetryRequest,
    TelemetrySample,
    TelemetrySeriesRequest,
    TelemetrySeriesSnapshot,
    TelemetrySourceType,
)


@runtime_checkable
class TelemetryPort(Protocol):
    def collect_sample(self, request: TelemetryRequest) -> TelemetrySample: ...

    def collect_series(
        self,
        request: TelemetrySeriesRequest,
    ) -> TelemetrySeriesSnapshot: ...

    def analyze_signal(
        self,
        request: TelemetryAnalysisRequest,
    ) -> TelemetryAnalysisResult: ...


@runtime_checkable
class TelemetrySourcePort(Protocol):
    @property
    def source_type(self) -> TelemetrySourceType: ...

    def read_sample(self, target_id: str) -> TelemetrySample: ...


@runtime_checkable
class TelemetryAuditSink(Protocol):
    def record(self, event: TelemetryAuditEvent) -> None: ...
