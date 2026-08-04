from __future__ import annotations

from ..contracts import HardwareObservationPort, ObservationSnapshot
from ..exceptions import ObservationUnavailable


class SerialObservationAdapter(HardwareObservationPort):
    def __init__(self, transport: object | None = None) -> None:
        self._transport = transport

    def read(self, device_reference: str) -> ObservationSnapshot:
        if self._transport is None:
            raise ObservationUnavailable()
        raise ObservationUnavailable()


__all__ = ["SerialObservationAdapter"]
