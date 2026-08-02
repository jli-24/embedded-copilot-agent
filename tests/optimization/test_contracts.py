from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.optimization import (
    OptimizationAlgorithm,
    OptimizationConstraint,
    OptimizationContextProjection,
    OptimizationMetric,
    OptimizationMetricUnit,
    OptimizationRequest,
    OptimizationTarget,
)

from .conftest import NOW, make_context, make_request


def test_contracts_are_frozen_strict_and_tuple_only(power_request) -> None:
    with pytest.raises(ValidationError):
        power_request.optimization_id = "changed"
    with pytest.raises(ValidationError):
        OptimizationRequest(
            optimization_id="optimization-1",
            hardware_context=make_context(),
            target=OptimizationTarget.POWER,
            algorithm=OptimizationAlgorithm.POWER_MODEL,
            baseline_metrics=list(power_request.baseline_metrics),
            constraints=power_request.constraints,
            timestamp=NOW,
        )
    with pytest.raises(ValidationError):
        type(power_request).model_validate(
            {**power_request.model_dump(mode="python"), "command": "unsafe"}
        )


@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_metric_rejects_boolean_and_non_finite_values(value) -> None:
    with pytest.raises(ValidationError):
        OptimizationMetric(name="power", value=value, unit=OptimizationMetricUnit.WATTS)


def test_context_fingerprint_is_deterministic_and_tamper_evident() -> None:
    context = make_context()
    assert (
        OptimizationContextProjection.model_validate(context.model_copy(deep=True))
        == context
    )
    with pytest.raises(ValidationError):
        OptimizationContextProjection.model_validate(
            context.model_copy(update={"summary": "Changed."})
        )


def test_request_rejects_naive_time_unsorted_and_duplicate_collections() -> None:
    request = make_request()
    with pytest.raises(ValidationError):
        type(request)(
            **{
                **request.model_dump(mode="python"),
                "timestamp": datetime(2026, 8, 2, 8, 0),
            }
        )
    with pytest.raises(ValidationError):
        type(request)(
            **{
                **request.model_dump(mode="python"),
                "baseline_metrics": tuple(reversed(request.baseline_metrics)),
            }
        )
    duplicate = request.constraints + request.constraints
    with pytest.raises(ValidationError):
        type(request)(**{**request.model_dump(mode="python"), "constraints": duplicate})


def test_constraint_requires_finite_ordered_bounds() -> None:
    with pytest.raises(ValidationError):
        OptimizationConstraint(
            parameter="power_scale",
            current=1.0,
            minimum=2.0,
            maximum=1.0,
            unit=OptimizationMetricUnit.RATIO,
        )


def test_target_algorithm_matrix_is_fixed() -> None:
    with pytest.raises(ValidationError):
        make_request(
            target=OptimizationTarget.POWER,
            algorithm=OptimizationAlgorithm.PERFORMANCE_MODEL,
        )
