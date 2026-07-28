from __future__ import annotations

from embedded_copilot.debug_runtime.adapters.base import ReadOnlyDebugAdapter
from embedded_copilot.debug_runtime.exceptions import DebugObservationRejected
from embedded_copilot.debug_runtime.models import (
    DebugSnapshotRequest,
    DebugSourceType,
    FrozenDebugSnapshot,
    RegisterObservation,
    RegisterRecord,
    StackFrameObservation,
    StackFrameRecord,
)
from embedded_copilot.debug_runtime.snapshot import build_snapshot
from embedded_copilot.debug_runtime.telemetry import build_telemetry


class GDBDebugAdapter(ReadOnlyDebugAdapter):
    __slots__ = ()

    def snapshot(self, request: DebugSnapshotRequest) -> FrozenDebugSnapshot:
        capture = self.capture(request.target_id)
        if any(
            not isinstance(item, (RegisterRecord, StackFrameRecord))
            for item in capture.observations
        ):
            raise DebugObservationRejected
        registers = tuple(
            sorted(
                (
                    item
                    for item in capture.observations
                    if isinstance(item, RegisterRecord)
                ),
                key=lambda item: item.register.casefold(),
            )
        )
        frames = tuple(
            sorted(
                (
                    item
                    for item in capture.observations
                    if isinstance(item, StackFrameRecord)
                ),
                key=lambda item: item.frame_index,
            )
        )
        if (
            len(registers) > 64
            or len(frames) > 64
            or len({item.register.casefold() for item in registers}) != len(registers)
            or len({item.frame_index for item in frames}) != len(frames)
        ):
            raise DebugObservationRejected
        observations = (
            *(
                RegisterObservation(register=item.register, value=item.value)
                for item in registers
            ),
            *(
                StackFrameObservation(
                    frame_index=item.frame_index,
                    function=item.function,
                    address=item.address,
                )
                for item in frames
            ),
        )
        telemetry = build_telemetry(
            target_id=request.target_id,
            source_type=DebugSourceType.GDB,
            captured_at=request.observed_at,
            metrics=capture.telemetry,
        )
        return build_snapshot(
            snapshot_id=request.snapshot_id,
            target_identity=capture.target_identity,
            observations=tuple(observations),
            telemetry=telemetry,
            source_type=DebugSourceType.GDB,
        )
