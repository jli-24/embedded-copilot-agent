"""Stable facade for the Engineering Interface Runtime."""

from __future__ import annotations

from typing import NoReturn

from embedded_copilot.engineering_interface.contracts import EngineeringInterfacePort


class EngineeringInterfaceRuntime:
    __slots__ = ("__port",)

    def __init__(self, *args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise TypeError("use create_engineering_interface_runtime")

    @classmethod
    def _compose(cls, port: EngineeringInterfacePort) -> EngineeringInterfaceRuntime:
        runtime = object.__new__(cls)
        runtime.__port = port
        return runtime

    def engineering_interface_port(self) -> EngineeringInterfacePort:
        return self.__port
