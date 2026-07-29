from __future__ import annotations

from .ports import EngineeringMemoryPort


class EngineeringMemory:
    __slots__ = ("_port",)

    def __init__(self, port: EngineeringMemoryPort) -> None:
        raise TypeError("EngineeringMemory must be created by its factory")

    @classmethod
    def _compose(cls, port: EngineeringMemoryPort) -> "EngineeringMemory":
        instance = object.__new__(cls)
        instance._port = port
        return instance

    def memory_port(self) -> EngineeringMemoryPort:
        return self._port
