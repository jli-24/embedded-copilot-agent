"""Typed Agent Execution and Human Loop integration tests."""

from __future__ import annotations

import pytest

from embedded_copilot.agent_execution import (
    AgentExecutionInputContext,
    AgentExecutionRequest,
    AgentExecutionResultStatus,
    AgentExecutionSnapshot,
    AgentExecutionState,
    ExecutionArtifactReference,
    ExecutionContextReference,
    ExecutionContextSourceType,
    ExecutionMetric,
    ExecutionMetricUnit,
    ExecutionResultProjection,
    agent_execution_result_fingerprint,
    agent_execution_snapshot_fingerprint,
)
from embedded_copilot.execution_runtime import (
    ExecutorType,
    ExecutionRejected,
    project_agent_execution_snapshot,
)
from embedded_copilot.engineering_generation import ArtifactType
from embedded_copilot.human_loop import (
    ProposalProjection,
    proposal_projection_fingerprint,
)

from .conftest import NOW


def _proposal() -> ProposalProjection:
    references = ("proposal-reference-1",)
    return ProposalProjection(
        proposal_id="proposal-1",
        artifact_type=ArtifactType.FIRMWARE,
        artifact_version=1,
        summary="Approved firmware proposal.",
        reference_ids=references,
        fingerprint=proposal_projection_fingerprint(
            proposal_id="proposal-1",
            artifact_type=ArtifactType.FIRMWARE,
            artifact_version=1,
            summary="Approved firmware proposal.",
            reference_ids=references,
        ),
    )


def _agent_snapshot(state=AgentExecutionState.SUCCESS) -> AgentExecutionSnapshot:
    context = AgentExecutionInputContext(
        context_id="context-1",
        summary="Safe planning context.",
        references=(
            ExecutionContextReference(
                source_type=ExecutionContextSourceType.PROJECT,
                reference_id="context-reference-1",
            ),
        ),
    )
    request = AgentExecutionRequest(
        execution_id="agent-execution-1",
        workflow_id="workflow-1",
        task_id="task-1",
        agent_type="FIRMWARE_AGENT",
        input_context=context,
        constraints=(),
        timestamp=NOW,
    )
    artifacts = (
        ExecutionArtifactReference(
            reference_id="artifact-1", artifact_type="FIRMWARE", status="READY"
        ),
    )
    metrics = (
        ExecutionMetric(name="warnings_count", value=0, unit=ExecutionMetricUnit.COUNT),
    )
    result_fp = agent_execution_result_fingerprint(
        execution_id=request.execution_id,
        workflow_id=request.workflow_id,
        task_id=request.task_id,
        agent_type=request.agent_type,
        status=AgentExecutionResultStatus.SUCCESS,
        summary="Agent produced a safe proposal.",
        artifacts=artifacts,
        metrics=metrics,
    )
    projection = ExecutionResultProjection(
        status=AgentExecutionResultStatus.SUCCESS,
        summary="Agent produced a safe proposal.",
        artifacts=artifacts,
        metrics=metrics,
        fingerprint=result_fp,
    )
    fp = agent_execution_snapshot_fingerprint(
        execution_id=request.execution_id,
        workflow_id=request.workflow_id,
        task_id=request.task_id,
        agent_type=request.agent_type,
        request=request,
        state=state,
        attempt=1,
        result_projection=projection if state is AgentExecutionState.SUCCESS else None,
        failure_code=None,
        progress_sequence=5,
    )
    return AgentExecutionSnapshot(
        execution_id=request.execution_id,
        workflow_id=request.workflow_id,
        task_id=request.task_id,
        agent_type=request.agent_type,
        request=request,
        state=state,
        attempt=1,
        result_projection=projection if state is AgentExecutionState.SUCCESS else None,
        failure_code=None,
        progress_sequence=5,
        fingerprint=fp,
    )


def test_agent_snapshot_projection_is_typed_safe_and_deterministic() -> None:
    snapshot = _agent_snapshot()
    proposal = _proposal()
    before_snapshot = snapshot.model_dump_json()
    before_proposal = proposal.model_dump_json()
    request = project_agent_execution_snapshot(
        snapshot,
        proposal=proposal,
        execution_id="controlled-execution-1",
        executor_type=ExecutorType.BUILD,
        timestamp=NOW,
    )
    assert request.workflow_id == snapshot.workflow_id
    assert request.task_id == snapshot.task_id
    assert request.agent_type == snapshot.agent_type
    assert request.context.summary == snapshot.result_projection.summary
    assert request.context.reference_ids == (
        "artifact-1",
        "context-reference-1",
        "proposal-reference-1",
    )
    assert request.proposal.proposal_id == proposal.proposal_id
    assert snapshot.model_dump_json() == before_snapshot
    assert proposal.model_dump_json() == before_proposal


def test_non_success_or_untyped_agent_snapshot_is_rejected() -> None:
    proposal = _proposal()
    with pytest.raises(ExecutionRejected):
        project_agent_execution_snapshot(
            _agent_snapshot(AgentExecutionState.READY),
            proposal=proposal,
            execution_id="controlled-execution-1",
            executor_type=ExecutorType.BUILD,
            timestamp=NOW,
        )
    with pytest.raises(ExecutionRejected):
        project_agent_execution_snapshot(
            {"state": "SUCCESS"},
            proposal=proposal,
            execution_id="controlled-execution-1",
            executor_type=ExecutorType.BUILD,
            timestamp=NOW,
        )


def test_projection_does_not_expose_artifact_body_or_runtime_objects() -> None:
    request = project_agent_execution_snapshot(
        _agent_snapshot(),
        proposal=_proposal(),
        execution_id="controlled-execution-1",
        executor_type=ExecutorType.BUILD,
        timestamp=NOW,
    )
    serialized = request.model_dump_json().lower()
    for forbidden in (
        "artifact_body",
        "stdout",
        "stderr",
        "executor_metadata",
        "live_executor",
        "provider",
    ):
        assert forbidden not in serialized
