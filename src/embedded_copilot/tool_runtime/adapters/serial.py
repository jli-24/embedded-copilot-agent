from __future__ import annotations

import copy

from embedded_copilot.debug_runtime import (
    DebugObservationTimeout,
    DebugPort,
    DebugSnapshotRequest,
    DebugSourceType,
    FrozenDebugSnapshot,
    UARTObservation,
)
from embedded_copilot.tool_runtime.models import (
    ReadSerialLogArguments,
    SerialLogLine,
    SerialLogOutput,
    SerialSeverity,
    SerialSeverityCount,
    ToolAdapterResult,
    ToolExecutionContext,
    ToolMetric,
    ToolMetricUnit,
    ToolResultStatus,
)
from embedded_copilot.tool_runtime.ports import EngineeringToolPort


class _SerialLogAdapter:
    __slots__ = ("_debug_port",)

    def __init__(self, debug_port: DebugPort) -> None:
        self._debug_port = debug_port

    @property
    def tool_name(self) -> str:
        return "read_serial_log"

    def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        arguments = context.request.arguments
        if not isinstance(arguments, ReadSerialLogArguments):
            return ToolAdapterResult(
                status=ToolResultStatus.REJECTED,
                summary="arguments_mismatch",
            )
        try:
            snapshot = self._debug_port.collect_snapshot(
                DebugSnapshotRequest(
                    snapshot_id=context.request.request_id,
                    target_id=arguments.target_id,
                    source_type=DebugSourceType.UART,
                    observed_at=context.requested_at,
                )
            )
        except DebugObservationTimeout:
            raise TimeoutError from None
        snapshot = FrozenDebugSnapshot.model_validate(
            copy.deepcopy(snapshot.model_dump(mode="python"))
        )
        if (
            snapshot.snapshot_id != context.request.request_id
            or snapshot.source_type is not DebugSourceType.UART
            or snapshot.telemetry.target_id != arguments.target_id
            or snapshot.telemetry.captured_at != context.requested_at
        ):
            raise ValueError("debug snapshot binding is invalid")
        lines = tuple(
            sorted(
                (
                    SerialLogLine(
                        sequence=item.sequence,
                        timestamp=item.timestamp,
                        severity=SerialSeverity(item.severity.value),
                        log_line=item.log_line,
                    )
                    for item in snapshot.observations
                    if isinstance(item, UARTObservation)
                ),
                key=lambda item: (item.sequence, item.timestamp),
            )
        )
        severity_summary = tuple(
            SerialSeverityCount(
                severity=severity,
                count=sum(item.severity is severity for item in lines),
            )
            for severity in SerialSeverity
        )
        return ToolAdapterResult(
            status=ToolResultStatus.SUCCESS,
            summary="serial_log_collected",
            output=SerialLogOutput(
                lines=lines,
                severity_summary=severity_summary,
            ),
            metrics=tuple(
                ToolMetric(
                    name=f"{severity.value.casefold()}_count",
                    value=sum(item.severity is severity for item in lines),
                    unit=ToolMetricUnit.COUNT,
                )
                for severity in sorted(SerialSeverity, key=lambda item: item.value)
            ),
        )


def create_serial_log_adapter(*, debug_port: DebugPort) -> EngineeringToolPort:
    if not isinstance(debug_port, DebugPort):
        raise TypeError("debug port is invalid")
    return _SerialLogAdapter(debug_port)
