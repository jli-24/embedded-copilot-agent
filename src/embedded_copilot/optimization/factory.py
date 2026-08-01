"""Composition entry for caller-owned Optimization Runtime dependencies."""

from embedded_copilot.optimization.contracts import (
    OptimizationEvaluationPort,
    OptimizationProgressSink,
    OptimizationRegistryPort,
)
from embedded_copilot.optimization.facade import OptimizationRuntime
from embedded_copilot.optimization.runtime import _OptimizationService


def create_optimization_runtime(
    *,
    optimizer_registry: OptimizationRegistryPort,
    evaluator: OptimizationEvaluationPort,
    progress_sink: OptimizationProgressSink,
) -> OptimizationRuntime:
    if not isinstance(optimizer_registry, OptimizationRegistryPort):
        raise TypeError("optimizer_registry must satisfy OptimizationRegistryPort")
    if not isinstance(evaluator, OptimizationEvaluationPort):
        raise TypeError("evaluator must satisfy OptimizationEvaluationPort")
    if not isinstance(progress_sink, OptimizationProgressSink):
        raise TypeError("progress_sink must satisfy OptimizationProgressSink")
    service = _OptimizationService(
        registry=optimizer_registry,
        evaluator=evaluator,
        progress_sink=progress_sink,
    )
    return OptimizationRuntime._compose(service)
