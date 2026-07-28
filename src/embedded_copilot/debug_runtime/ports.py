from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.debug_runtime.models import (
    DebugAuditEvent,
    DebugSnapshotRequest,
    DebugSourceCapture,
    DebugSourceType,
    FrozenDebugSnapshot,
    TargetIdentificationRequest,
    TargetIdentity,
    TelemetryMetric,
    TelemetryRequest,
    TelemetrySnapshot,
)


@runtime_checkable
class DebugPort(Protocol):
    def identify_target(
        self, request: TargetIdentificationRequest
    ) -> TargetIdentity: ...

    def collect_snapshot(
        self, request: DebugSnapshotRequest
    ) -> FrozenDebugSnapshot: ...

    def collect_telemetry(self, request: TelemetryRequest) -> TelemetrySnapshot: ...


@runtime_checkable
class DebugSourcePort(Protocol):
    @property
    def source_type(self) -> DebugSourceType: ...

    def read_identity(self, target_id: str) -> TargetIdentity: ...

    def read_snapshot(self, target_id: str) -> DebugSourceCapture: ...

    def read_telemetry(self, target_id: str) -> tuple[TelemetryMetric, ...]: ...


@runtime_checkable
class DebugAuditSink(Protocol):
    def record(self, event: DebugAuditEvent) -> None: ...
