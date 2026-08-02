"""Stateless PID mathematical candidate projection."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, field_validator

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
    optimization_proposal_fingerprint,
)


class PIDGainParameters(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
        hide_input_in_errors=True,
    )

    kp: float
    ki: float
    kd: float

    @field_validator("kp", "ki", "kd")
    @classmethod
    def _finite_gain(cls, value: float) -> float:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("PID gain must be finite")
        return value


class _PIDOptimizer:
    def __init__(
        self,
        *,
        gains: PIDGainParameters,
        output_min: float,
        output_max: float,
    ) -> None:
        self._gains = PIDGainParameters.model_validate(gains.model_copy(deep=True))
        ranges = tuple(
            sorted(
                (
                    OptimizationParameterRange(
                        parameter="controller_output",
                        minimum=output_min,
                        maximum=output_max,
                        unit=OptimizationMetricUnit.RATIO,
                    ),
                    OptimizationParameterRange(
                        parameter="kd",
                        minimum=gains.kd,
                        maximum=gains.kd,
                        unit=OptimizationMetricUnit.RATIO,
                    ),
                    OptimizationParameterRange(
                        parameter="ki",
                        minimum=gains.ki,
                        maximum=gains.ki,
                        unit=OptimizationMetricUnit.RATIO,
                    ),
                    OptimizationParameterRange(
                        parameter="kp",
                        minimum=gains.kp,
                        maximum=gains.kp,
                        unit=OptimizationMetricUnit.RATIO,
                    ),
                ),
                key=lambda item: item.parameter,
            )
        )
        self._metadata = OptimizationAlgorithmMetadata(
            algorithm=OptimizationAlgorithm.PID,
            target=OptimizationTarget.BALANCED,
            parameter_space=ranges,
            objective="BALANCE_CONTROL_ERROR",
            fingerprint=optimization_algorithm_metadata_fingerprint(
                algorithm=OptimizationAlgorithm.PID,
                target=OptimizationTarget.BALANCED,
                parameter_space=ranges,
                objective="BALANCE_CONTROL_ERROR",
            ),
        )

    @property
    def metadata(self) -> OptimizationAlgorithmMetadata:
        return self._metadata.model_copy(deep=True)

    def propose(self, request: OptimizationInvocationRequest) -> OptimizationProposal:
        plan = request.plan
        metrics = {item.name: item for item in plan.request.baseline_metrics}
        if tuple(sorted(metrics)) != ("error", "previous_output"):
            raise ValueError("PID metrics rejected")
        error = metrics["error"]
        previous = metrics["previous_output"]
        if error.unit is not previous.unit:
            raise ValueError("PID units rejected")
        ranges = {item.parameter: item for item in plan.parameter_space}
        output_range = ranges["controller_output"]
        candidate = (
            previous.value
            + (self._gains.kp + self._gains.ki + self._gains.kd) * error.value
        )
        candidate = min(max(candidate, output_range.minimum), output_range.maximum)
        projected = (
            error.model_copy(deep=True),
            OptimizationMetric(
                name="previous_output", value=candidate, unit=previous.unit
            ),
        )
        changes = (
            OptimizationParameterChange(
                parameter="controller_output",
                before=previous.value,
                after=candidate,
                unit=previous.unit,
            ),
        )
        return _proposal(
            request=request,
            changes=changes,
            metrics=projected,
            gain=0.0,
            risk=OptimizationRiskLevel.MEDIUM,
        )


def create_pid_optimizer(
    *, gains: PIDGainParameters, output_min: float, output_max: float
) -> _PIDOptimizer:
    if type(gains) is not PIDGainParameters:
        raise TypeError("gains must be a typed PIDGainParameters")
    if (
        type(output_min) is not float
        or type(output_max) is not float
        or not math.isfinite(output_min)
        or not math.isfinite(output_max)
        or output_min > output_max
    ):
        raise ValueError("PID output range is invalid")
    return _PIDOptimizer(gains=gains, output_min=output_min, output_max=output_max)


def _proposal(
    *,
    request: OptimizationInvocationRequest,
    changes: tuple[OptimizationParameterChange, ...],
    metrics: tuple[OptimizationMetric, ...],
    gain: float,
    risk: OptimizationRiskLevel,
) -> OptimizationProposal:
    values = dict(
        optimization_id=request.plan.request.optimization_id,
        plan_fingerprint=request.plan.fingerprint,
        candidate_semantics="unverified",
        parameter_changes=changes,
        expected_gain=gain,
        risk_level=risk,
        metrics_projection=metrics,
    )
    return OptimizationProposal(
        **values,
        fingerprint=optimization_proposal_fingerprint(**values),
    )
