"""Stable Hardware Engineering facade."""

from __future__ import annotations

from typing import NoReturn

from embedded_copilot.engineering_hardware.contracts import HardwareEngineeringPort


class EngineeringHardwareRuntime:
    __slots__ = ("__port",)

    def __init__(self, *args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise TypeError("use create_engineering_hardware_runtime")

    @classmethod
    def _compose(cls, port: HardwareEngineeringPort) -> EngineeringHardwareRuntime:
        runtime = object.__new__(cls)
        runtime.__port = port
        return runtime

    def hardware_engineering_port(self) -> HardwareEngineeringPort:
        return self.__port
