from __future__ import annotations

from ..contracts import (
    ConnectionStatus,
    DeviceConnection,
    DevicePort,
    DeviceType,
)


class FakeDeviceAdapter(DevicePort):
    def connect(self, device_reference: str) -> DeviceConnection:
        return DeviceConnection.create(
            device_id=device_reference,
            device_type=DeviceType.ESP32,
            connection_status=ConnectionStatus.CONNECTED,
        )


__all__ = ["FakeDeviceAdapter"]
