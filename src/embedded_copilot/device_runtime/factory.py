from __future__ import annotations

from .adapters.serial import SerialDeviceAdapter
from .contracts import DevicePort
from .service import DeviceRuntimeService


def create_device_runtime(port: DevicePort | None = None) -> DeviceRuntimeService:
    return DeviceRuntimeService(port or SerialDeviceAdapter())


__all__ = ["create_device_runtime"]
