from __future__ import annotations

import pytest

from embedded_copilot.agent_execution import (
    AgentExecutionResultStatus,
    AgentExecutionState,
    ExecutionFailureCode,
    ExecutionProgressUnavailable,
    ExecutionVerificationStatus,
    create_agent_execution_runtime,
)

from .conftest import (
    RecordingAgent,
    RecordingProgressSink,
    RecordingVerifier,
    StaticRegistry,
    binding_for,
    result_for,
)


def _runtime(request, *, agent=None, registry=None, verifier=None, sink=None):
    selected_agent = agent or RecordingAgent(result_for(request))
    selected_registry = registry or StaticRegistry(binding_for(selected_agent))
    selected_verifier = verifier or RecordingVerifier()
    selected_sink = sink or RecordingProgressSink()
    runtime = create_agent_execution_runtime(
        agent_registry=selected_registry,
        progress_sink=selected_sink,
        verification_port=selected_verifier,
    )
    return (
        runtime,
        selected_agent,
        selected_registry,
        selected_verifier,
        selected_sink,
    )


def test_success_lifecycle_is_deterministic_and_calls_each_port_once(
    execution_request,
) -> None:
    runtime, agent, registry, verifier, sink = _runtime(execution_request)

    snapshot = runtime.execution_port().execute_task(execution_request)

    assert snapshot.state is AgentExecutionState.SUCCESS
    assert snapshot.attempt == 1
    assert snapshot.result_projection is not None
    assert [event.state for event in sink.events] == [
        AgentExecutionState.CREATED,
        AgentExecutionState.READY,
        AgentExecutionState.RUNNING,
        AgentExecutionState.VERIFYING,
        AgentExecutionState.SUCCESS,
    ]
    assert len(agent.calls) == len(registry.calls) == len(verifier.calls) == 1
    assert snapshot.request is not execution_request


@pytest.mark.parametrize(
    ("error", "state", "failure"),
    (
        (
            RuntimeError("provider secret"),
            AgentExecutionState.FAILED,
            ExecutionFailureCode.AGENT_UNAVAILABLE,
        ),
        (
            TimeoutError("transport path"),
            AgentExecutionState.TIMEOUT,
            ExecutionFailureCode.AGENT_TIMEOUT,
        ),
    ),
)
def test_agent_failures_return_sanitized_snapshots(
    execution_request,
    error,
    state,
    failure,
) -> None:
    agent = RecordingAgent(error=error)
    runtime, *_ = _runtime(execution_request, agent=agent)

    snapshot = runtime.execution_port().execute_task(execution_request)

    assert snapshot.state is state
    assert snapshot.failure_code is failure
    assert "secret" not in snapshot.model_dump_json()
    assert "path" not in snapshot.model_dump_json()


def test_unknown_agent_and_registry_failure_do_not_fallback(execution_request) -> None:
    for registry in (
        StaticRegistry(binding=None),
        StaticRegistry(error=RuntimeError("database unavailable")),
    ):
        runtime, agent, _, verifier, _ = _runtime(
            execution_request,
            registry=registry,
        )

        snapshot = runtime.execution_port().execute_task(execution_request)

        assert snapshot.state is AgentExecutionState.FAILED
        assert snapshot.failure_code is ExecutionFailureCode.AGENT_UNAVAILABLE
        assert agent.calls == []
        assert verifier.calls == []


def test_agent_type_mismatch_is_rejected_without_invocation(execution_request) -> None:
    agent = RecordingAgent(result_for(execution_request))
    registry = StaticRegistry(binding_for(agent, agent_type="DEBUG"))
    runtime, _, _, verifier, _ = _runtime(execution_request, registry=registry)

    snapshot = runtime.execution_port().execute_task(execution_request)

    assert snapshot.state is AgentExecutionState.FAILED
    assert snapshot.failure_code is ExecutionFailureCode.AGENT_UNAVAILABLE
    assert agent.calls == []
    assert verifier.calls == []


def test_untyped_agent_result_fails_closed(execution_request) -> None:
    agent = RecordingAgent({"status": "SUCCESS", "payload": "unsafe"})
    runtime, _, _, verifier, _ = _runtime(execution_request, agent=agent)

    snapshot = runtime.execution_port().execute_task(execution_request)

    assert snapshot.state is AgentExecutionState.FAILED
    assert snapshot.failure_code is ExecutionFailureCode.AGENT_RESULT_REJECTED
    assert verifier.calls == []


def test_invalid_verification_discards_result_projection(execution_request) -> None:
    verifier = RecordingVerifier(status=ExecutionVerificationStatus.INVALID)
    runtime, *_ = _runtime(execution_request, verifier=verifier)

    snapshot = runtime.execution_port().execute_task(execution_request)

    assert snapshot.state is AgentExecutionState.FAILED
    assert snapshot.failure_code is ExecutionFailureCode.VERIFICATION_INVALID
    assert snapshot.result_projection is None


def test_verification_failure_is_sanitized(execution_request) -> None:
    verifier = RecordingVerifier(error=RuntimeError("database secret path"))
    runtime, *_ = _runtime(execution_request, verifier=verifier)

    snapshot = runtime.execution_port().execute_task(execution_request)

    assert snapshot.state is AgentExecutionState.FAILED
    assert snapshot.failure_code is ExecutionFailureCode.VERIFICATION_UNAVAILABLE
    assert "database" not in snapshot.model_dump_json()
    assert snapshot.result_projection is None


def test_agent_domain_failure_is_verified_then_returns_failed_snapshot(
    execution_request,
) -> None:
    agent = RecordingAgent(
        result_for(execution_request, status=AgentExecutionResultStatus.FAILED)
    )
    runtime, *_ = _runtime(execution_request, agent=agent)

    snapshot = runtime.execution_port().execute_task(execution_request)

    assert snapshot.state is AgentExecutionState.FAILED
    assert snapshot.failure_code is ExecutionFailureCode.AGENT_FAILED
    assert snapshot.result_projection is not None


def test_progress_failure_stops_before_downstream_calls(execution_request) -> None:
    sink = RecordingProgressSink(fail_at=2)
    runtime, agent, registry, verifier, _ = _runtime(execution_request, sink=sink)

    with pytest.raises(ExecutionProgressUnavailable) as error:
        runtime.execution_port().execute_task(execution_request)

    assert str(error.value) == "execution progress is unavailable"
    assert len(registry.calls) == 1
    assert agent.calls == []
    assert verifier.calls == []
