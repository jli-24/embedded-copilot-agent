from __future__ import annotations

from embedded_copilot.debug_runtime.adapters.base import ReadOnlyDebugAdapter
from embedded_copilot.debug_runtime.exceptions import DebugObservationRejected
from embedded_copilot.debug_runtime.models import (
    DebugSnapshotRequest,
    FrozenDebugSnapshot,
    RegisterObservation,
    RegisterRecord,
)
from embedded_copilot.debug_runtime.snapshot import build_snapshot
from embedded_copilot.debug_runtime.telemetry import build_telemetry


class JLinkDebugAdapter(ReadOnlyDebugAdapter):
    __slots__ = ()

    def snapshot(self, request: DebugSnapshotRequest) -> FrozenDebugSnapshot:
        capture = self.capture(request.target_id)
        if len(capture.observations) > 64 or any(
            not isinstance(item, RegisterRecord) for item in capture.observations
        ):
            raise DebugObservationRejected
        records = tuple(
            sorted(capture.observations, key=lambda item: item.register.casefold())
        )
        names = tuple(item.register.casefold() for item in records)
        if len(names) != len(set(names)):
            raise DebugObservationRejected
        observations = tuple(
            RegisterObservation(register=item.register, value=item.value)
            for item in records
        )
        telemetry = build_telemetry(
            target_id=request.target_id,
            source_type=self.source_type,
            captured_at=request.observed_at,
            metrics=capture.telemetry,
        )
        return build_snapshot(
            snapshot_id=request.snapshot_id,
            target_identity=capture.target_identity,
            observations=observations,
            telemetry=telemetry,
            source_type=self.source_type,
        )
