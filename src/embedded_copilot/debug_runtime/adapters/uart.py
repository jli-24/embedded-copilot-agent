from __future__ import annotations

from embedded_copilot.debug_runtime.adapters.base import ReadOnlyDebugAdapter
from embedded_copilot.debug_runtime.exceptions import DebugObservationRejected
from embedded_copilot.debug_runtime.models import (
    DebugSeverity,
    DebugSnapshotRequest,
    DebugSourceType,
    FrozenDebugSnapshot,
    UARTLogRecord,
    UARTObservation,
)
from embedded_copilot.debug_runtime.snapshot import build_snapshot
from embedded_copilot.debug_runtime.telemetry import build_telemetry

_CRITICAL_MARKERS = ("panic", "fatal", "hardfault", "guru meditation")
_ERROR_MARKERS = ("error", "failed", "fault")
_WARNING_MARKERS = ("warn", "timeout", "overrun")


class UARTDebugAdapter(ReadOnlyDebugAdapter):
    __slots__ = ()

    def snapshot(self, request: DebugSnapshotRequest) -> FrozenDebugSnapshot:
        capture = self.capture(request.target_id)
        if len(capture.observations) > 256 or any(
            not isinstance(item, UARTLogRecord) for item in capture.observations
        ):
            raise DebugObservationRejected
        records = tuple(sorted(capture.observations, key=lambda item: item.sequence))
        sequences = tuple(item.sequence for item in records)
        if len(sequences) != len(set(sequences)):
            raise DebugObservationRejected
        observations = tuple(
            UARTObservation(
                sequence=item.sequence,
                timestamp=item.timestamp,
                severity=_severity(item.log_line),
                log_line=item.log_line,
            )
            for item in records
        )
        telemetry = build_telemetry(
            target_id=request.target_id,
            source_type=DebugSourceType.UART,
            captured_at=request.observed_at,
            metrics=capture.telemetry,
        )
        return build_snapshot(
            snapshot_id=request.snapshot_id,
            target_identity=capture.target_identity,
            observations=observations,
            telemetry=telemetry,
            source_type=DebugSourceType.UART,
        )


def _severity(line: str) -> DebugSeverity:
    normalized = line.casefold()
    if any(marker in normalized for marker in _CRITICAL_MARKERS):
        return DebugSeverity.CRITICAL
    if any(marker in normalized for marker in _ERROR_MARKERS):
        return DebugSeverity.ERROR
    if any(marker in normalized for marker in _WARNING_MARKERS):
        return DebugSeverity.WARNING
    if "debug" in normalized:
        return DebugSeverity.DEBUG
    return DebugSeverity.INFO
