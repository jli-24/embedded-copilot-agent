"""Safe projection from public Hardware Intelligence observations."""

from __future__ import annotations

from datetime import datetime

from embedded_copilot.hardware_intelligence import (
    HardwareContextProjection,
    HardwareMetricUnit,
    HardwareObservation,
    hardware_observation_fingerprint,
)
from embedded_copilot.optimization.exceptions import OptimizationRejected
from embedded_copilot.optimization.models import (
    OptimizationAlgorithm,
    OptimizationConstraint,
    OptimizationContextProjection,
    OptimizationMetric,
    OptimizationMetricUnit,
    OptimizationRequest,
    OptimizationTarget,
    optimization_context_fingerprint,
)

_UNITS = {
    HardwareMetricUnit.COUNT: OptimizationMetricUnit.COUNT,
    HardwareMetricUnit.PERCENT: OptimizationMetricUnit.PERCENT,
    HardwareMetricUnit.CELSIUS: OptimizationMetricUnit.CELSIUS,
    HardwareMetricUnit.VOLTS: OptimizationMetricUnit.VOLTS,
    HardwareMetricUnit.AMPERES: OptimizationMetricUnit.AMPERES,
    HardwareMetricUnit.HERTZ: OptimizationMetricUnit.HERTZ,
    HardwareMetricUnit.RPM: OptimizationMetricUnit.RPM,
}


def project_hardware_observation(
    observations: tuple[HardwareObservation, ...],
    *,
    optimization_id: str,
    hardware_context: HardwareContextProjection,
    constraints: tuple[OptimizationConstraint, ...],
    optimization_target: OptimizationTarget,
    algorithm: OptimizationAlgorithm,
    timestamp: datetime,
) -> OptimizationRequest:
    """Project typed observations without retaining hardware runtime objects."""
    try:
        if type(observations) is not tuple or not 1 <= len(observations) <= 64:
            raise ValueError("observations rejected")
        if type(constraints) is not tuple:
            raise ValueError("constraints rejected")
        if type(hardware_context) is not HardwareContextProjection:
            raise ValueError("hardware context rejected")
        context = HardwareContextProjection.model_validate(
            hardware_context.model_copy(deep=True)
        )
        copied = tuple(_copy_observation(item) for item in observations)
        names = tuple(item.metric_name for item in copied)
        if len(names) != len(set(names)):
            raise ValueError("duplicate metric")

        metrics = {
            item.metric_name: OptimizationMetric(
                name=item.metric_name,
                value=item.value,
                unit=_UNITS[item.unit],
            )
            for item in copied
        }
        if optimization_target is OptimizationTarget.POWER:
            required = {"current", "temperature", "voltage"}
            if not required.issubset(metrics):
                raise ValueError("power observation incomplete")
            metrics["power"] = OptimizationMetric(
                name="power",
                value=metrics["voltage"].value * metrics["current"].value,
                unit=OptimizationMetricUnit.WATTS,
            )
        elif optimization_target is OptimizationTarget.PERFORMANCE:
            if not {
                "cpu_usage",
                "latency",
                "memory_usage",
                "throughput",
            }.issubset(metrics):
                raise ValueError("performance observation incomplete")
        elif not {"error", "previous_output"}.issubset(metrics):
            raise ValueError("balanced observation incomplete")

        references = tuple(
            sorted((context.fingerprint, hardware_observation_fingerprint(copied)))
        )
        summary = "Hardware observation projection."
        projected_context = OptimizationContextProjection(
            context_id=context.hardware_id,
            summary=summary,
            reference_ids=references,
            fingerprint=optimization_context_fingerprint(
                context_id=context.hardware_id,
                summary=summary,
                reference_ids=references,
            ),
        )
        return OptimizationRequest(
            optimization_id=optimization_id,
            hardware_context=projected_context,
            target=optimization_target,
            algorithm=algorithm,
            baseline_metrics=tuple(
                sorted(metrics.values(), key=lambda item: item.name)
            ),
            constraints=tuple(
                sorted(
                    (
                        OptimizationConstraint.model_validate(
                            item.model_copy(deep=True)
                        )
                        for item in constraints
                    ),
                    key=lambda item: item.parameter,
                )
            ),
            timestamp=timestamp,
        )
    except OptimizationRejected:
        raise
    except Exception:
        raise OptimizationRejected("hardware observation rejected") from None


def _copy_observation(value: object) -> HardwareObservation:
    if type(value) is not HardwareObservation:
        raise ValueError("observation must be typed")
    return HardwareObservation.model_validate(value.model_copy(deep=True))
