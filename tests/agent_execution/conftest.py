from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.agent_execution import (
    AgentBindingMetadata,
    AgentCapabilityBinding,
    AgentExecutionInputContext,
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentExecutionResultStatus,
    ExecutionApprovalContext,
    ExecutionApprovalDecision,
    ExecutionContextReference,
    ExecutionContextSourceType,
    ExecutionVerificationResult,
    ExecutionVerificationStatus,
    agent_binding_fingerprint,
    agent_execution_result_fingerprint,
    execution_verification_result_fingerprint,
)

NOW = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def request_for(*, agent_type: str = "FIRMWARE") -> AgentExecutionRequest:
    return AgentExecutionRequest(
        execution_id="execution-1",
        workflow_id="workflow-1",
        task_id="task-a",
        agent_type=agent_type,
        input_context=AgentExecutionInputContext(
            context_id="context-1",
            summary="Review the task using verified context references.",
            references=(
                ExecutionContextReference(
                    source_type=ExecutionContextSourceType.WORKFLOW,
                    reference_id="workflow-reference-1",
                ),
            ),
        ),
        constraints=("Do not execute external engineering tools.",),
        timestamp=NOW,
    )


def result_for(
    request: AgentExecutionRequest,
    *,
    status: AgentExecutionResultStatus = AgentExecutionResultStatus.SUCCESS,
) -> AgentExecutionResult:
    values = {
        "execution_id": request.execution_id,
        "workflow_id": request.workflow_id,
        "task_id": request.task_id,
        "agent_type": request.agent_type,
        "status": status,
        "summary": "Agent execution produced a reviewable projection.",
        "artifacts": (),
        "metrics": (),
    }
    return AgentExecutionResult(
        **values,
        fingerprint=agent_execution_result_fingerprint(**values),
    )


class RecordingAgent:
    def __init__(self, result=None, *, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def binding_for(agent: RecordingAgent, *, agent_type: str = "FIRMWARE"):
    values = {
        "binding_id": f"binding-{agent_type.lower()}",
        "agent_type": agent_type,
        "capabilities": ("EXECUTE_TASK",),
    }
    metadata = AgentBindingMetadata(
        **values,
        fingerprint=agent_binding_fingerprint(**values),
    )
    return AgentCapabilityBinding(metadata=metadata, execution_port=agent)


class StaticRegistry:
    def __init__(self, binding=None, *, error: Exception | None = None) -> None:
        self.binding = binding
        self.error = error
        self.calls = []

    def resolve(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.binding


class RecordingVerifier:
    def __init__(
        self,
        *,
        status: ExecutionVerificationStatus = ExecutionVerificationStatus.VALID,
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.error = error
        self.calls = []

    def verify(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        values = {
            "execution_id": request.execution_id,
            "result_fingerprint": request.result.fingerprint,
            "status": self.status,
        }
        return ExecutionVerificationResult(
            **values,
            fingerprint=execution_verification_result_fingerprint(**values),
        )


class RecordingProgressSink:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.events = []
        self.fail_at = fail_at

    def emit(self, event):
        if event.sequence == self.fail_at:
            raise RuntimeError("database path C:/secret and token=private")
        self.events.append(event)


def approval_for(snapshot, decision: ExecutionApprovalDecision):
    return ExecutionApprovalContext(
        execution_id=snapshot.execution_id,
        workflow_id=snapshot.workflow_id,
        task_id=snapshot.task_id,
        agent_type=snapshot.agent_type,
        attempt=snapshot.attempt,
        snapshot_fingerprint=snapshot.fingerprint,
        decision=decision,
        reviewer="engineer-1",
        reviewed_at=REVIEWED_AT,
    )


@pytest.fixture
def execution_request() -> AgentExecutionRequest:
    return request_for()
