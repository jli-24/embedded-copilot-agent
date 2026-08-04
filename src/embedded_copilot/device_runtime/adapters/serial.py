from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts import DeviceConnection, DevicePort, validate_device_connection
from ..exceptions import DeviceUnavailable


@runtime_checkable
class SerialTransport(Protocol):
    def connect(self, device_reference: str) -> DeviceConnection: ...


class SerialDeviceAdapter(DevicePort):
    def __init__(self, transport: SerialTransport | None = None) -> None:
        self._transport = transport

    def connect(self, device_reference: str) -> DeviceConnection:
        if self._transport is None:
            raise DeviceUnavailable()
        try:
            return validate_device_connection(self._transport.connect(device_reference))
        except DeviceUnavailable:
            raise
        except Exception as error:
            raise DeviceUnavailable() from error


__all__ = ["SerialDeviceAdapter", "SerialTransport"]
