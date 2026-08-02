from __future__ import annotations

import ast
import inspect

import pytest

from embedded_copilot.workflow_runtime import (
    EngineeringWorkflowPlan,
    FrozenWorkflowSnapshot,
    RequirementSpecification,
    WorkflowApprovalDecision,
    WorkflowApprovalRejected,
    WorkflowContextProjection,
    WorkflowPreparationRequest,
    WorkflowProgressUnavailable,
    WorkflowRiskItem,
    WorkflowSourceType,
    WorkflowState,
    create_workflow_runtime,
)
from embedded_copilot.workflow_runtime import runtime as runtime_module

from .conftest import NOW, approval_for, context_for


class RequirementAgent:
    def __init__(self, result: RequirementSpecification) -> None:
        self.result = result
        self.calls = []

    def analyze(self, request):
        self.calls.append(request)
        return self.result


class ContextPort:
    def __init__(self, result: WorkflowContextProjection) -> None:
        self.result = result
        self.calls = []

    def resolve(self, request):
        self.calls.append(request)
        return self.result


class PlanningAgent:
    def __init__(self, result: EngineeringWorkflowPlan) -> None:
        self.result = result
        self.calls = []

    def plan(self, request):
        self.calls.append(request)
        return self.result


class ProgressSink:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.events = []
        self.fail_at = fail_at

    def emit(self, event):
        if event.sequence == self.fail_at:
            raise RuntimeError("database path and secret payload")
        self.events.append(event)


def _runtime(requirements, context, plan, *, sink=None):
    requirement_agent = RequirementAgent(requirements)
    context_port = ContextPort(context)
    planning_agent = PlanningAgent(plan)
    progress_sink = sink or ProgressSink()
    runtime = create_workflow_runtime(
        requirement_agent=requirement_agent,
        planning_agent=planning_agent,
        context_port=context_port,
        progress_sink=progress_sink,
    )
    return runtime, requirement_agent, context_port, planning_agent, progress_sink


def _prepare(port):
    return port.prepare_workflow(
        WorkflowPreparationRequest(
            workflow_id="workflow-1",
            requirement_summary="Plan a reviewable embedded engineering workflow.",
            requested_at=NOW,
        )
    )


def test_prepare_and_schedule_are_deterministic(
    requirements,
    context,
    plan,
) -> None:
    runtime, requirement_agent, context_port, planning_agent, sink = _runtime(
        requirements,
        context,
        plan,
    )
    port = runtime.workflow_port()

    waiting = _prepare(port)

    assert waiting.state is WorkflowState.WAITING_APPROVAL
    assert waiting.schedule == ()
    assert waiting.requirements is not requirements
    assert waiting.context is not context
    assert len(requirement_agent.calls) == 1
    assert len(context_port.calls) == 1
    assert len(planning_agent.calls) == 1
    assert planning_agent.calls[0].risks == waiting.risks
    assert [item.sequence for item in sink.events] == list(range(1, 8))

    scheduled = port.schedule_workflow(waiting, approval_for(waiting))

    assert scheduled.state is WorkflowState.SCHEDULED
    assert tuple(batch.task_ids for batch in scheduled.schedule) == (
        ("task-a",),
        ("task-b", "task-c"),
        ("task-d",),
    )
    assert sink.events[-1].sequence == 8
    assert scheduled.progress_sequence == 8


def test_scheduler_is_independent_of_risk_projection(
    requirements,
    plan,
) -> None:
    with_risk = context_for(requirements)
    without_risk = context_for(requirements, risks=())
    first, *_ = _runtime(requirements, with_risk, plan)
    second, *_ = _runtime(requirements, without_risk, plan)

    first_waiting = _prepare(first.workflow_port())
    second_waiting = _prepare(second.workflow_port())
    first_result = first.workflow_port().schedule_workflow(
        first_waiting,
        approval_for(first_waiting),
    )
    second_result = second.workflow_port().schedule_workflow(
        second_waiting,
        approval_for(second_waiting),
    )

    assert first_result.schedule == second_result.schedule
    source = inspect.getsource(runtime_module.build_schedule)
    assert "risk" not in source.casefold()


def test_denied_approval_returns_rejected_snapshot(
    requirements,
    context,
    plan,
) -> None:
    runtime, *_ = _runtime(requirements, context, plan)
    waiting = _prepare(runtime.workflow_port())

    rejected = runtime.workflow_port().schedule_workflow(
        waiting,
        approval_for(waiting, decision=WorkflowApprovalDecision.DENIED),
    )

    assert rejected.state is WorkflowState.REJECTED
    assert rejected.schedule == ()


def test_approval_binding_mismatch_fails_closed(
    requirements,
    context,
    plan,
) -> None:
    runtime, *_ = _runtime(requirements, context, plan)
    waiting = _prepare(runtime.workflow_port())
    approval = approval_for(waiting).model_copy(
        update={"waiting_snapshot_fingerprint": "sha256:" + "0" * 64}
    )

    with pytest.raises(WorkflowApprovalRejected):
        runtime.workflow_port().schedule_workflow(waiting, approval)


def test_progress_failure_stops_before_downstream_calls(
    requirements,
    context,
    plan,
) -> None:
    sink = ProgressSink(fail_at=3)
    runtime, requirement_agent, context_port, planning_agent, _ = _runtime(
        requirements,
        context,
        plan,
        sink=sink,
    )

    with pytest.raises(WorkflowProgressUnavailable) as error:
        _prepare(runtime.workflow_port())

    assert str(error.value) == "workflow progress is unavailable"
    assert len(requirement_agent.calls) == 1
    assert len(context_port.calls) == 1
    assert planning_agent.calls == []


def test_tampered_typed_output_is_revalidated(
    requirements,
    context,
    plan,
) -> None:
    tampered = requirements.model_copy(update={"fingerprint": "sha256:" + "0" * 64})
    runtime, *_ = _runtime(tampered, context, plan)

    with pytest.raises(Exception) as error:
        _prepare(runtime.workflow_port())

    assert "0" * 64 not in str(error.value)


def test_typed_outputs_are_not_reconstructed_through_serialization() -> None:
    tree = ast.parse(inspect.getsource(runtime_module._typed_copy))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "model_copy" in called
    assert "model_dump" not in called
    assert "model_dump_json" not in called
    assert "model_validate_json" not in called


def test_facade_does_not_expose_composition_state(
    requirements,
    context,
    plan,
) -> None:
    runtime, *_ = _runtime(requirements, context, plan)

    assert runtime.workflow_port() is not None
    for name in (
        "requirement_agent",
        "planning_agent",
        "context_port",
        "progress_sink",
        "scheduler",
        "risk",
    ):
        assert not hasattr(runtime, name)


def test_context_port_is_external_composition_boundary() -> None:
    source = inspect.getsource(runtime_module)
    assert "knowledge.intelligence" not in source
    assert "engineering_memory" not in source


def test_risk_must_bind_to_verified_context_source(
    requirements,
    plan,
) -> None:
    invalid_risk = WorkflowRiskItem(
        risk_type="POWER_BUDGET_UNKNOWN",
        source_type=WorkflowSourceType.KNOWLEDGE_CONTEXT,
        source_id="unknown-source",
        confidence=1.0,
        reference="https://example.invalid/unknown",
    )
    context = context_for(requirements, risks=(invalid_risk,))
    runtime, *_ = _runtime(requirements, context, plan)

    with pytest.raises(Exception):
        _prepare(runtime.workflow_port())


def test_public_snapshot_rejects_tampering(
    requirements,
    context,
    plan,
) -> None:
    runtime, *_ = _runtime(requirements, context, plan)
    waiting = _prepare(runtime.workflow_port())
    tampered = waiting.model_copy(update={"progress_sequence": 99})

    with pytest.raises(Exception):
        FrozenWorkflowSnapshot.model_validate(tampered)

    with pytest.raises(WorkflowApprovalRejected):
        runtime.workflow_port().schedule_workflow(tampered, approval_for(waiting))
