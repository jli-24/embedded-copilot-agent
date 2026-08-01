"""Execution Integration projection tests."""

from __future__ import annotations

import pytest

from embedded_copilot.execution_runtime import (
    ExecutionArtifactReference,
    ExecutionContextProjection,
    ExecutorType,
    ExecutionMetric,
    ExecutionMetricUnit,
    ExecutionPlan,
    ExecutionProposalReference,
    ExecutionResultProjection,
    ExecutionResultStatus,
    ExecutionSnapshot,
    ExecutionState,
    ExecutionVerificationProjection,
    ExecutionVerificationStatus,
    execution_context_fingerprint,
    execution_plan_fingerprint,
    execution_result_fingerprint,
    execution_snapshot_fingerprint,
    execution_verification_fingerprint,
)
from embedded_copilot.hardware_intelligence import (
    HardwareIntelligenceRejected,
    project_execution_snapshot,
)

from .conftest import NOW


def _execution_snapshot(state=ExecutionState.SUCCESS) -> ExecutionSnapshot:
    context = ExecutionContextProjection(
        context_id="agent-execution-1",
        summary="Safe execution context.",
        reference_ids=("input-reference-1",),
        fingerprint=execution_context_fingerprint(
            context_id="agent-execution-1",
            summary="Safe execution context.",
            reference_ids=("input-reference-1",),
        ),
    )
    proposal = ExecutionProposalReference(
        proposal_id="proposal-1",
        proposal_fingerprint="sha256:" + "a" * 64,
    )
    plan = ExecutionPlan(
        execution_id="controlled-execution-1",
        workflow_id="workflow-1",
        task_id="task-1",
        agent_type="HARDWARE_AGENT",
        executor_type=ExecutorType.VERIFY,
        context=context,
        proposal=proposal,
        prepared_at=NOW,
        fingerprint=execution_plan_fingerprint(
            execution_id="controlled-execution-1",
            workflow_id="workflow-1",
            task_id="task-1",
            agent_type="HARDWARE_AGENT",
            executor_type=ExecutorType.VERIFY,
            context=context,
            proposal=proposal,
            prepared_at=NOW,
        ),
    )
    artifacts = (
        ExecutionArtifactReference(
            reference_id="artifact-reference-1",
            artifact_type="HARDWARE_REPORT",
            status="READY",
        ),
    )
    metrics = (
        ExecutionMetric(name="checks_count", value=3, unit=ExecutionMetricUnit.COUNT),
    )
    result = ExecutionResultProjection(
        status=ExecutionResultStatus.SUCCESS,
        summary="Controlled execution completed.",
        artifacts=artifacts,
        metrics=metrics,
        fingerprint=execution_result_fingerprint(
            status=ExecutionResultStatus.SUCCESS,
            summary="Controlled execution completed.",
            artifacts=artifacts,
            metrics=metrics,
        ),
    )
    verification = ExecutionVerificationProjection(
        execution_id=plan.execution_id,
        result_fingerprint=result.fingerprint,
        status=ExecutionVerificationStatus.VALID,
        fingerprint=execution_verification_fingerprint(
            execution_id=plan.execution_id,
            result_fingerprint=result.fingerprint,
            status=ExecutionVerificationStatus.VALID,
        ),
    )
    failure_code = None
    if state is not ExecutionState.SUCCESS:
        result = None
        verification = None
    fingerprint = execution_snapshot_fingerprint(
        plan=plan,
        state=state,
        approval_fingerprint="sha256:" + "b" * 64,
        result=result,
        verification=verification,
        failure_code=failure_code,
        progress_sequence=6,
    )
    return ExecutionSnapshot(
        plan=plan,
        state=state,
        approval_fingerprint="sha256:" + "b" * 64,
        result=result,
        verification=verification,
        failure_code=failure_code,
        progress_sequence=6,
        fingerprint=fingerprint,
    )


def test_successful_execution_projects_safe_hardware_request() -> None:
    snapshot = _execution_snapshot()
    before = snapshot.model_dump_json()
    request = project_execution_snapshot(
        snapshot,
        hardware_id="hardware-analysis-1",
        device_type="ESP32_S3",
        board_reference="board-reference-1",
        scenario_id="scenario-1",
        timestamp=NOW,
    )
    assert request.hardware_id == "hardware-analysis-1"
    assert request.context.device_type == "ESP32_S3"
    values = {item.key: item.value for item in request.context.safe_metadata}
    assert values["execution_id"] == snapshot.plan.execution_id
    assert values["reference_000"] == "artifact-reference-1"
    assert snapshot.model_dump_json() == before


def test_non_success_or_untyped_execution_snapshot_is_rejected() -> None:
    with pytest.raises(HardwareIntelligenceRejected):
        project_execution_snapshot(
            _execution_snapshot(ExecutionState.READY),
            hardware_id="hardware-analysis-1",
            device_type="ESP32_S3",
            board_reference="board-reference-1",
            scenario_id="scenario-1",
            timestamp=NOW,
        )
    with pytest.raises(HardwareIntelligenceRejected):
        project_execution_snapshot(
            {"state": "SUCCESS"},
            hardware_id="hardware-analysis-1",
            device_type="ESP32_S3",
            board_reference="board-reference-1",
            scenario_id="scenario-1",
            timestamp=NOW,
        )


def test_execution_projection_contains_no_hardware_action_or_artifact_body() -> None:
    request = project_execution_snapshot(
        _execution_snapshot(),
        hardware_id="hardware-analysis-1",
        device_type="ESP32_S3",
        board_reference="board-reference-1",
        scenario_id="scenario-1",
        timestamp=NOW,
    )
    serialized = request.model_dump_json().lower()
    for forbidden in (
        "artifact_body",
        "command",
        "device_handle",
        "serial_port",
        "flash",
        "reset",
    ):
        assert forbidden not in serialized
