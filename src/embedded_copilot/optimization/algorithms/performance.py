"""Deterministic performance candidate projection."""

from embedded_copilot.optimization.algorithms.pid import _proposal
from embedded_copilot.optimization.models import (
    OptimizationAlgorithm,
    OptimizationAlgorithmMetadata,
    OptimizationInvocationRequest,
    OptimizationMetric,
    OptimizationMetricUnit,
    OptimizationParameterChange,
    OptimizationParameterRange,
    OptimizationProposal,
    OptimizationRiskLevel,
    OptimizationTarget,
    optimization_algorithm_metadata_fingerprint,
)


class _PerformanceOptimizer:
    def __init__(self) -> None:
        ranges = (
            OptimizationParameterRange(
                parameter="performance_scale",
                minimum=1.05,
                maximum=1.05,
                unit=OptimizationMetricUnit.RATIO,
            ),
        )
        self._metadata = OptimizationAlgorithmMetadata(
            algorithm=OptimizationAlgorithm.PERFORMANCE_MODEL,
            target=OptimizationTarget.PERFORMANCE,
            parameter_space=ranges,
            objective="MAXIMIZE_PERFORMANCE",
            fingerprint=optimization_algorithm_metadata_fingerprint(
                algorithm=OptimizationAlgorithm.PERFORMANCE_MODEL,
                target=OptimizationTarget.PERFORMANCE,
                parameter_space=ranges,
                objective="MAXIMIZE_PERFORMANCE",
            ),
        )

    @property
    def metadata(self) -> OptimizationAlgorithmMetadata:
        return self._metadata.model_copy(deep=True)

    def propose(self, request: OptimizationInvocationRequest) -> OptimizationProposal:
        metrics = {item.name: item for item in request.plan.request.baseline_metrics}
        if tuple(sorted(metrics)) != (
            "cpu_usage",
            "latency",
            "memory_usage",
            "throughput",
        ):
            raise ValueError("performance metrics rejected")
        if (
            metrics["latency"].unit is not OptimizationMetricUnit.MILLISECONDS
            or metrics["throughput"].unit is not OptimizationMetricUnit.HERTZ
            or metrics["cpu_usage"].unit is not OptimizationMetricUnit.PERCENT
            or metrics["memory_usage"].unit is not OptimizationMetricUnit.PERCENT
        ):
            raise ValueError("performance units rejected")
        scale_range = next(
            item
            for item in request.plan.parameter_space
            if item.parameter == "performance_scale"
        )
        scale = scale_range.minimum
        projected = tuple(
            sorted(
                (
                    metrics["cpu_usage"].model_copy(deep=True),
                    OptimizationMetric(
                        name="latency",
                        value=metrics["latency"].value / scale,
                        unit=OptimizationMetricUnit.MILLISECONDS,
                    ),
                    metrics["memory_usage"].model_copy(deep=True),
                    OptimizationMetric(
                        name="throughput",
                        value=metrics["throughput"].value * scale,
                        unit=OptimizationMetricUnit.HERTZ,
                    ),
                ),
                key=lambda item: item.name,
            )
        )
        return _proposal(
            request=request,
            changes=(
                OptimizationParameterChange(
                    parameter="performance_scale",
                    before=1.0,
                    after=scale,
                    unit=OptimizationMetricUnit.RATIO,
                ),
            ),
            metrics=projected,
            gain=5.0,
            risk=OptimizationRiskLevel.LOW,
        )


def create_performance_optimizer() -> _PerformanceOptimizer:
    return _PerformanceOptimizer()
