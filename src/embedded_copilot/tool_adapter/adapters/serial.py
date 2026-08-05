from __future__ import annotations

from embedded_copilot.hardware_observation.contracts import (
    ObservationSnapshot,
    validate_observation_snapshot,
)

from ..exceptions import ObservationUnavailable
from ..executor import SerialTransportPort


class SerialToolAdapter:
    def __init__(self, transport: SerialTransportPort | None = None) -> None:
        self._transport = transport

    def get_device(self, project_id: str) -> object:
        if self._transport is None:
            raise ObservationUnavailable()
        try:
            method = getattr(self._transport, "observe", None) or getattr(
                self._transport, "read", None
            )
            if not callable(method):
                raise ValueError("serial transport is unavailable")
            result = method(project_id)
            if type(result) is not ObservationSnapshot:
                raise ValueError("observation projection is invalid")
            return validate_observation_snapshot(result)
        except Exception as error:
            raise ObservationUnavailable() from error

    def observe(self, device_reference: str) -> object:
        return self.get_device(device_reference)


SerialAdapter = SerialToolAdapter

__all__ = ["SerialAdapter", "SerialToolAdapter"]
