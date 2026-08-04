from __future__ import annotations

import copy

from .contracts import (
    HardwareObservationPort,
    ObservationSnapshot,
    validate_observation_snapshot,
)
from .exceptions import ObservationRejected
from .models import identifier


class HardwareObservationService:
    __slots__ = ("_port",)

    def __init__(self, port: HardwareObservationPort) -> None:
        if not isinstance(port, HardwareObservationPort):
            raise TypeError("observation port is invalid")
        self._port = port

    def read(self, device_reference: str) -> ObservationSnapshot:
        try:
            reference = identifier(device_reference, field="device_reference")
            return validate_observation_snapshot(
                self._port.read(copy.deepcopy(reference))
            )
        except ObservationRejected:
            raise
        except Exception as error:
            raise ObservationRejected() from error
