from __future__ import annotations

import pytest

from embedded_copilot.optimization import (
    OptimizationAlgorithm,
    OptimizationState,
    OptimizationTarget,
    create_optimization_runtime,
)
from embedded_copilot.optimization.algorithms.performance import (
    create_performance_optimizer,
)
from embedded_copilot.optimization.algorithms.pid import (
    PIDGainParameters,
    create_pid_optimizer,
)
from embedded_copilot.optimization.algorithms.power import create_power_optimizer
from embedded_copilot.optimization.evaluation.service import (
    create_deterministic_evaluator,
)

from .conftest import RecordingProgressSink, StaticRegistry, make_request


def _plan(request, optimizer):
    runtime = create_optimization_runtime(
        optimizer_registry=StaticRegistry(optimizer),
        evaluator=create_deterministic_evaluator(),
        progress_sink=RecordingProgressSink(),
    )
    return runtime.optimization_port().create_plan(request)


def _metrics(snapshot):
    return {item.name: item.value for item in snapshot.proposal.metrics_projection}


def test_pid_formula_is_bounded_deterministic_and_stateless() -> None:
    request = make_request(OptimizationTarget.BALANCED, OptimizationAlgorithm.PID)
    before = request.model_dump_json()
    optimizer = create_pid_optimizer(
        gains=PIDGainParameters(kp=1.0, ki=0.5, kd=0.25),
        output_min=-10.0,
        output_max=3.0,
    )
    first = _plan(request, optimizer)
    second = _plan(request, optimizer)
    assert first.state is OptimizationState.PLANNED
    assert _metrics(first)["previous_output"] == pytest.approx(3.0)
    assert first.proposal == second.proposal
    assert request.model_dump_json() == before


def test_power_projection_reduces_candidate_without_temperature_inference() -> None:
    snapshot = _plan(make_request(), create_power_optimizer())
    metrics = _metrics(snapshot)
    assert metrics["current"] == pytest.approx(1.9)
    assert metrics["power"] == pytest.approx(9.5)
    assert metrics["voltage"] == 5.0
    assert metrics["temperature"] == 30.0
    assert snapshot.proposal.candidate_semantics == "unverified"


def test_performance_projection_uses_fixed_scale_without_resource_inference() -> None:
    request = make_request(
        OptimizationTarget.PERFORMANCE,
        OptimizationAlgorithm.PERFORMANCE_MODEL,
    )
    snapshot = _plan(request, create_performance_optimizer())
    metrics = _metrics(snapshot)
    assert metrics["latency"] == pytest.approx(100.0 / 1.05)
    assert metrics["throughput"] == pytest.approx(105.0)
    assert metrics["cpu_usage"] == 40.0
    assert metrics["memory_usage"] == 50.0


def test_evaluation_zero_baseline_has_no_percent_change() -> None:
    request = make_request(OptimizationTarget.BALANCED, OptimizationAlgorithm.PID)
    request = request.model_copy(
        update={
            "baseline_metrics": tuple(
                item.model_copy(update={"value": 0.0})
                for item in request.baseline_metrics
            )
        }
    )
    optimizer = create_pid_optimizer(
        gains=PIDGainParameters(kp=1.0, ki=0.0, kd=0.0),
        output_min=-10.0,
        output_max=10.0,
    )
    runtime = create_optimization_runtime(
        optimizer_registry=StaticRegistry(optimizer),
        evaluator=create_deterministic_evaluator(),
        progress_sink=RecordingProgressSink(),
    )
    evaluated = runtime.optimization_port().evaluate(
        runtime.optimization_port().create_plan(request)
    )
    assert all(item.percent_change is None for item in evaluated.evaluation.improvement)
