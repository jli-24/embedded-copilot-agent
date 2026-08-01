"""Deterministic power candidate projection."""

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


class _PowerOptimizer:
    def __init__(self) -> None:
        ranges = (
            OptimizationParameterRange(
                parameter="power_scale",
                minimum=0.95,
                maximum=0.95,
                unit=OptimizationMetricUnit.RATIO,
            ),
        )
        self._metadata = OptimizationAlgorithmMetadata(
            algorithm=OptimizationAlgorithm.POWER_MODEL,
            target=OptimizationTarget.POWER,
            parameter_space=ranges,
            objective="MINIMIZE_POWER",
            fingerprint=optimization_algorithm_metadata_fingerprint(
                algorithm=OptimizationAlgorithm.POWER_MODEL,
                target=OptimizationTarget.POWER,
                parameter_space=ranges,
                objective="MINIMIZE_POWER",
            ),
        )

    @property
    def metadata(self) -> OptimizationAlgorithmMetadata:
        return self._metadata.model_copy(deep=True)

    def propose(self, request: OptimizationInvocationRequest) -> OptimizationProposal:
        metrics = {item.name: item for item in request.plan.request.baseline_metrics}
        if tuple(sorted(metrics)) != (
            "current",
            "power",
            "temperature",
            "voltage",
        ):
            raise ValueError("power metrics rejected")
        if (
            metrics["current"].unit is not OptimizationMetricUnit.AMPERES
            or metrics["power"].unit is not OptimizationMetricUnit.WATTS
            or metrics["temperature"].unit is not OptimizationMetricUnit.CELSIUS
            or metrics["voltage"].unit is not OptimizationMetricUnit.VOLTS
        ):
            raise ValueError("power units rejected")
        scale_range = next(
            item
            for item in request.plan.parameter_space
            if item.parameter == "power_scale"
        )
        scale = scale_range.minimum
        current = metrics["current"].value * scale
        power = metrics["voltage"].value * current
        projected = tuple(
            sorted(
                (
                    OptimizationMetric(
                        name="current",
                        value=current,
                        unit=OptimizationMetricUnit.AMPERES,
                    ),
                    OptimizationMetric(
                        name="power", value=power, unit=OptimizationMetricUnit.WATTS
                    ),
                    metrics["temperature"].model_copy(deep=True),
                    metrics["voltage"].model_copy(deep=True),
                ),
                key=lambda item: item.name,
            )
        )
        return _proposal(
            request=request,
            changes=(
                OptimizationParameterChange(
                    parameter="power_scale",
                    before=1.0,
                    after=scale,
                    unit=OptimizationMetricUnit.RATIO,
                ),
            ),
            metrics=projected,
            gain=5.0,
            risk=OptimizationRiskLevel.LOW,
        )


def create_power_optimizer() -> _PowerOptimizer:
    return _PowerOptimizer()
