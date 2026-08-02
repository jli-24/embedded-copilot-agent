from __future__ import annotations

import pytest

from embedded_copilot.agent_execution import (
    AgentExecutionState,
    ExecutionApprovalDecision,
    ExecutionRecoveryRejected,
    create_agent_execution_runtime,
)

from .conftest import (
    RecordingAgent,
    RecordingProgressSink,
    RecordingVerifier,
    StaticRegistry,
    approval_for,
    binding_for,
    result_for,
)


class RecoveringRegistry:
    def __init__(self, first, second) -> None:
        self.bindings = [first, second]
        self.calls = []

    def resolve(self, request):
        self.calls.append(request)
        return self.bindings[len(self.calls) - 1]


def test_two_stage_human_approved_recovery_runs_at_most_twice(
    execution_request,
) -> None:
    first = RecordingAgent(error=RuntimeError("unavailable"))
    second = RecordingAgent(result_for(execution_request))
    registry = RecoveringRegistry(binding_for(first), binding_for(second))
    sink = RecordingProgressSink()
    runtime = create_agent_execution_runtime(
        agent_registry=registry,
        progress_sink=sink,
        verification_port=RecordingVerifier(),
    )
    port = runtime.execution_port()

    failed = port.execute_task(execution_request)
    waiting = port.resume_execution(
        failed,
        approval_for(failed, ExecutionApprovalDecision.REQUESTED),
    )
    recovered = port.resume_execution(
        waiting,
        approval_for(waiting, ExecutionApprovalDecision.APPROVED),
    )

    assert failed.state is AgentExecutionState.FAILED
    assert waiting.state is AgentExecutionState.WAIT_HUMAN
    assert recovered.state is AgentExecutionState.SUCCESS
    assert recovered.attempt == 2
    assert len(registry.calls) == 2
    assert len(first.calls) == len(second.calls) == 1


def test_denied_recovery_is_cancelled(execution_request) -> None:
    agent = RecordingAgent(error=RuntimeError("unavailable"))
    runtime = create_agent_execution_runtime(
        agent_registry=StaticRegistry(binding_for(agent)),
        progress_sink=RecordingProgressSink(),
        verification_port=RecordingVerifier(),
    )
    port = runtime.execution_port()
    failed = port.execute_task(execution_request)
    waiting = port.resume_execution(
        failed,
        approval_for(failed, ExecutionApprovalDecision.REQUESTED),
    )

    cancelled = port.resume_execution(
        waiting,
        approval_for(waiting, ExecutionApprovalDecision.DENIED),
    )

    assert cancelled.state is AgentExecutionState.CANCELLED


def test_approval_binding_and_replay_are_rejected(execution_request) -> None:
    agent = RecordingAgent(error=RuntimeError("unavailable"))
    runtime = create_agent_execution_runtime(
        agent_registry=StaticRegistry(binding_for(agent)),
        progress_sink=RecordingProgressSink(),
        verification_port=RecordingVerifier(),
    )
    port = runtime.execution_port()
    failed = port.execute_task(execution_request)
    waiting = port.resume_execution(
        failed,
        approval_for(failed, ExecutionApprovalDecision.REQUESTED),
    )

    with pytest.raises(ExecutionRecoveryRejected):
        port.resume_execution(
            waiting,
            approval_for(failed, ExecutionApprovalDecision.APPROVED),
        )


def test_second_failure_cannot_be_recovered(execution_request) -> None:
    first = RecordingAgent(error=RuntimeError("first"))
    second = RecordingAgent(error=RuntimeError("second"))
    registry = RecoveringRegistry(binding_for(first), binding_for(second))
    runtime = create_agent_execution_runtime(
        agent_registry=registry,
        progress_sink=RecordingProgressSink(),
        verification_port=RecordingVerifier(),
    )
    port = runtime.execution_port()
    failed = port.execute_task(execution_request)
    waiting = port.resume_execution(
        failed,
        approval_for(failed, ExecutionApprovalDecision.REQUESTED),
    )
    failed_again = port.resume_execution(
        waiting,
        approval_for(waiting, ExecutionApprovalDecision.APPROVED),
    )

    assert failed_again.attempt == 2
    with pytest.raises(ExecutionRecoveryRejected):
        port.resume_execution(
            failed_again,
            approval_for(failed_again, ExecutionApprovalDecision.REQUESTED),
        )
