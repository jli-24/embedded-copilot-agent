from __future__ import annotations

import copy
from datetime import datetime

from pydantic import ValidationError

from embedded_copilot.debug_runtime.exceptions import DebugObservationRejected
from embedded_copilot.debug_runtime.models import (
    DebugSourceCapture,
    DebugSourceType,
    TargetIdentity,
    TelemetrySnapshot,
)
from embedded_copilot.debug_runtime.ports import DebugSourcePort
from embedded_copilot.debug_runtime.telemetry import build_telemetry


class ReadOnlyDebugAdapter:
    __slots__ = ("_source", "_source_type")

    def __init__(
        self,
        source: DebugSourcePort,
        source_type: DebugSourceType,
    ) -> None:
        self._source = source
        self._source_type = source_type

    @property
    def source_type(self) -> DebugSourceType:
        return self._source_type

    def identify(self, target_id: str) -> TargetIdentity:
        value = self._source.read_identity(target_id)
        return isolated_identity(value)

    def telemetry(
        self,
        target_id: str,
        captured_at: datetime,
    ) -> TelemetrySnapshot:
        return build_telemetry(
            target_id=target_id,
            source_type=self._source_type,
            captured_at=captured_at,
            metrics=self._source.read_telemetry(target_id),
        )

    def capture(self, target_id: str) -> DebugSourceCapture:
        value = self._source.read_snapshot(target_id)
        try:
            capture = DebugSourceCapture.model_validate(
                copy.deepcopy(value.model_dump(mode="python"))
            )
        except (AttributeError, TypeError, ValidationError):
            raise DebugObservationRejected from None
        if capture.source_type is not self._source_type:
            raise DebugObservationRejected
        return capture


def isolated_identity(value: object) -> TargetIdentity:
    try:
        return TargetIdentity.model_validate(
            copy.deepcopy(value.model_dump(mode="python"))
        )
    except (AttributeError, TypeError, ValidationError):
        raise DebugObservationRejected from None
