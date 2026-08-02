"""Narrow public facade for Optimization Runtime."""

from __future__ import annotations

from embedded_copilot.optimization.contracts import OptimizationPort


class OptimizationRuntime:
    __slots__ = ("_port",)

    def __init__(self) -> None:
        raise TypeError("use create_optimization_runtime")

    @classmethod
    def _compose(cls, port: OptimizationPort) -> OptimizationRuntime:
        runtime = object.__new__(cls)
        runtime._port = port
        return runtime

    def optimization_port(self) -> OptimizationPort:
        return self._port
