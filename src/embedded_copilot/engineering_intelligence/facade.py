"""Stable Engineering Intelligence facade."""

from __future__ import annotations

from typing import NoReturn

from embedded_copilot.engineering_intelligence.contracts import (
    EngineeringIntelligencePort,
)


class EngineeringIntelligenceRuntime:
    __slots__ = ("__port",)

    def __init__(self, *args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise TypeError("use create_engineering_intelligence_runtime")

    @classmethod
    def _compose(
        cls,
        port: EngineeringIntelligencePort,
    ) -> EngineeringIntelligenceRuntime:
        runtime = object.__new__(cls)
        runtime.__port = port
        return runtime

    def engineering_intelligence_port(self) -> EngineeringIntelligencePort:
        return self.__port
