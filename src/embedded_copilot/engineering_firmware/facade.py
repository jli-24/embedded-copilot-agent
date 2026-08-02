"""Narrow facade for Firmware Engineering."""

from __future__ import annotations

from embedded_copilot.engineering_firmware.contracts import FirmwareEngineeringPort


class EngineeringFirmwareRuntime:
    __slots__ = ("__port",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use create_engineering_firmware_runtime")

    @classmethod
    def _compose(cls, port: FirmwareEngineeringPort) -> EngineeringFirmwareRuntime:
        runtime = object.__new__(cls)
        runtime.__port = port
        return runtime

    def firmware_engineering_port(self) -> FirmwareEngineeringPort:
        return self.__port
