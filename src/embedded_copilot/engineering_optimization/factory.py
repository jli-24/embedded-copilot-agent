"""Composition entry point for Engineering Optimization."""

from embedded_copilot.engineering_optimization.facade import (
    EngineeringOptimizationRuntime,
)
from embedded_copilot.engineering_optimization.runtime import (
    _create_engineering_optimization_service,
)


def create_engineering_optimization_runtime() -> EngineeringOptimizationRuntime:
    return EngineeringOptimizationRuntime(_create_engineering_optimization_service())


__all__ = ("create_engineering_optimization_runtime",)
