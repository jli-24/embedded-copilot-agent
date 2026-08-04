from __future__ import annotations

import copy

from .contracts import DeviceConnection, DevicePort, validate_device_connection
from .exceptions import DeviceRequestRejected
from .models import identifier


class DeviceRuntimeService:
    __slots__ = ("_port",)

    def __init__(self, port: DevicePort) -> None:
        if not isinstance(port, DevicePort):
            raise TypeError("device port is invalid")
        self._port = port

    def connect(self, device_reference: str) -> DeviceConnection:
        try:
            reference = identifier(device_reference, field="device_reference")
            result = self._port.connect(copy.deepcopy(reference))
            return validate_device_connection(result)
        except DeviceRequestRejected:
            raise
        except (TypeError, ValueError) as error:
            raise DeviceRequestRejected() from error
