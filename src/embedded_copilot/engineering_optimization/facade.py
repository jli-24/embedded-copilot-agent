"""Public Engineering Optimization Runtime facade."""

from __future__ import annotations

from embedded_copilot.engineering_optimization.contracts import (
    EngineeringOptimizationPort,
)


class EngineeringOptimizationRuntime:
    __slots__ = ("__port",)

    def __init__(self, port: EngineeringOptimizationPort) -> None:
        self.__port = port

    def engineering_optimization_port(self) -> EngineeringOptimizationPort:
        return self.__port


__all__ = ("EngineeringOptimizationRuntime",)
