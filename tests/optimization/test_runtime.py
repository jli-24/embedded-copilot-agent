from __future__ import annotations

import pytest

from embedded_copilot.optimization import (
    OptimizationApprovalDecision,
    OptimizationFailureCode,
    OptimizationProgressUnavailable,
    OptimizationRejected,
    OptimizationState,
    create_optimization_runtime,
)
from embedded_copilot.optimization.algorithms.power import create_power_optimizer
from embedded_copilot.optimization.evaluation.service import (
    create_deterministic_evaluator,
)

from .conftest import (
    RecordingProgressSink,
    StaticRegistry,
    make_approval,
)


def _runtime(*, optimizer=None, evaluator=None, sink=None):
    optimizer = optimizer or create_power_optimizer()
    evaluator = evaluator or create_deterministic_evaluator()
    sink = sink or RecordingProgressSink()
    registry = StaticRegistry(optimizer)
    runtime = create_optimization_runtime(
        optimizer_registry=registry,
        evaluator=evaluator,
        progress_sink=sink,
    )
    return runtime, registry, evaluator, sink


def test_complete_lifecycle_and_exact_single_binding(power_request) -> None:
    runtime, registry, _, sink = _runtime()
    port = runtime.optimization_port()
    planned = port.create_plan(power_request)
    evaluated = port.evaluate(planned)
    terminal = port.approve(evaluated, make_approval(evaluated))
    assert terminal.state is OptimizationState.SUCCESS
    assert terminal.approval is not None
    assert len(registry.calls) == 1
    assert [event.state for event in sink.events] == [
        OptimizationState.CREATED,
        OptimizationState.PLANNED,
        OptimizationState.RUNNING,
        OptimizationState.EVALUATED,
        OptimizationState.APPROVED,
        OptimizationState.SUCCESS,
    ]


def test_rejected_approval_cancels_without_success(power_request) -> None:
    runtime, _, _, sink = _runtime()
    port = runtime.optimization_port()
    evaluated = port.evaluate(port.create_plan(power_request))
    terminal = port.approve(
        evaluated,
        make_approval(evaluated, OptimizationApprovalDecision.REJECTED),
    )
    assert terminal.state is OptimizationState.CANCELLED
    assert terminal.failure_code is OptimizationFailureCode.APPROVAL_REJECTED
    assert sink.events[-1].state is OptimizationState.CANCELLED


def test_duplicate_id_and_consumed_approval_are_rejected(power_request) -> None:
    runtime, *_ = _runtime()
    port = runtime.optimization_port()
    planned = port.create_plan(power_request)
    with pytest.raises(OptimizationRejected):
        port.create_plan(power_request)
    evaluated = port.evaluate(planned)
    approval = make_approval(evaluated)
    port.approve(evaluated, approval)
    with pytest.raises(OptimizationRejected):
        port.approve(evaluated, approval)


class BrokenOptimizer:
    metadata = create_power_optimizer().metadata

    def __init__(self, error=None, result=None) -> None:
        self.error = error
        self.result = result

    def propose(self, request):
        if self.error:
            raise self.error
        return self.result


class BrokenEvaluator:
    def __init__(self, error=None, result=None) -> None:
        self.error = error
        self.result = result

    def evaluate(self, request):
        if self.error:
            raise self.error
        return self.result


@pytest.mark.parametrize(
    ("error", "state", "code"),
    [
        (
            TimeoutError("private command"),
            OptimizationState.TIMEOUT,
            OptimizationFailureCode.OPTIMIZER_TIMEOUT,
        ),
        (None, OptimizationState.FAILED, OptimizationFailureCode.OPTIMIZER_REJECTED),
    ],
)
def test_optimizer_timeout_and_invalid_projection_are_sanitized(
    power_request, error, state, code
) -> None:
    runtime, *_ = _runtime(optimizer=BrokenOptimizer(error=error, result={}))
    terminal = runtime.optimization_port().create_plan(power_request)
    assert terminal.state is state
    assert terminal.failure_code is code
    assert "private" not in terminal.model_dump_json().lower()


def test_evaluator_failure_and_invalid_projection_fail_closed(power_request) -> None:
    for evaluator, code in (
        (
            BrokenEvaluator(error=RuntimeError("database secret")),
            OptimizationFailureCode.EVALUATOR_UNAVAILABLE,
        ),
        (BrokenEvaluator(result={}), OptimizationFailureCode.EVALUATION_INVALID),
    ):
        runtime, *_ = _runtime(evaluator=evaluator)
        planned = runtime.optimization_port().create_plan(power_request)
        terminal = runtime.optimization_port().evaluate(planned)
        assert terminal.state is OptimizationState.FAILED
        assert terminal.failure_code is code
        assert "database" not in terminal.model_dump_json().lower()


def test_progress_failure_stops_downstream_work(power_request) -> None:
    sink = RecordingProgressSink(fail_on_sequence=1)
    runtime, registry, _, _ = _runtime(sink=sink)
    with pytest.raises(OptimizationProgressUnavailable):
        runtime.optimization_port().create_plan(power_request)
    assert not registry.calls


def test_facade_hides_composition_dependencies() -> None:
    runtime, *_ = _runtime()
    assert runtime.optimization_port() is runtime.optimization_port()
    for name in ("optimizer_registry", "evaluator", "progress_sink", "ledger"):
        assert not hasattr(runtime, name)


def test_approval_binding_mismatch_is_rejected_before_terminal_progress(
    power_request,
) -> None:
    runtime, _, _, sink = _runtime()
    port = runtime.optimization_port()
    evaluated = port.evaluate(port.create_plan(power_request))
    approval = make_approval(evaluated).model_copy(
        update={"proposal_fingerprint": "sha256:" + "f" * 64}
    )
    with pytest.raises(OptimizationRejected):
        port.approve(evaluated, approval)
    assert sink.events[-1].state is OptimizationState.EVALUATED


def test_snapshot_from_another_runtime_is_not_consumable(power_request) -> None:
    first, *_ = _runtime()
    second, *_ = _runtime()
    evaluated = first.optimization_port().evaluate(
        first.optimization_port().create_plan(power_request)
    )
    with pytest.raises(OptimizationRejected):
        second.optimization_port().approve(evaluated, make_approval(evaluated))


def test_progress_failure_after_proposal_is_fail_closed(power_request) -> None:
    sink = RecordingProgressSink(fail_on_sequence=2)
    runtime, registry, _, _ = _runtime(sink=sink)
    with pytest.raises(OptimizationProgressUnavailable):
        runtime.optimization_port().create_plan(power_request)
    assert len(registry.calls) == 1
    with pytest.raises(OptimizationRejected):
        runtime.optimization_port().create_plan(power_request)


def test_factory_rejects_untyped_dependencies() -> None:
    with pytest.raises(TypeError):
        create_optimization_runtime(
            optimizer_registry=object(),
            evaluator=object(),
            progress_sink=object(),
        )
