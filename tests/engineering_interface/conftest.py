from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_generation import ArtifactType
from embedded_copilot.human_loop import (
    HumanLoopProgressEvent,
    HumanLoopProgressEventType,
    HumanLoopState,
    HumanReviewDecision,
    HumanReviewDecisionProjection,
    HumanReviewSnapshot,
    ProposalProjection,
    human_review_decision_fingerprint,
    human_review_snapshot_fingerprint,
    proposal_projection_fingerprint,
)
from embedded_copilot.workflow_runtime import (
    EngineeringWorkflowPlan,
    EngineeringWorkflowTask,
    FrozenTaskDAG,
    FrozenWorkflowSnapshot,
    RequirementSpecification,
    WorkflowContextProjection,
    WorkflowProgressEvent,
    WorkflowProgressEventType,
    WorkflowRiskProjection,
    WorkflowState,
    engineering_workflow_plan_fingerprint,
    requirement_specification_fingerprint,
    task_dag_fingerprint,
    workflow_context_fingerprint,
    workflow_risk_fingerprint,
    workflow_snapshot_fingerprint,
)

NOW = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def waiting_workflow_snapshot(
    workflow_id: str = "workflow-1",
) -> FrozenWorkflowSnapshot:
    requirement_values = ("Review the ESP32-S3 camera design.",)
    requirements = RequirementSpecification(
        workflow_id=workflow_id,
        requirements=requirement_values,
        constraints=(),
        assumptions=(),
        fingerprint=requirement_specification_fingerprint(
            workflow_id=workflow_id,
            requirements=requirement_values,
            constraints=(),
            assumptions=(),
        ),
    )
    context = WorkflowContextProjection(
        workflow_id=workflow_id,
        requirement_fingerprint=requirements.fingerprint,
        context_fingerprint=workflow_context_fingerprint(
            workflow_id=workflow_id,
            requirement_fingerprint=requirements.fingerprint,
            confidence=0.0,
            verified_source_references=(),
        ),
        confidence=0.0,
        verified_source_references=(),
        projected_risks=(),
    )
    risks = WorkflowRiskProjection(
        risks=(),
        fingerprint=workflow_risk_fingerprint(()),
    )
    tasks = (
        EngineeringWorkflowTask(
            task_id="task-1",
            summary="Review the design proposal.",
        ),
    )
    plan = EngineeringWorkflowPlan(
        workflow_id=workflow_id,
        plan_id="plan-1",
        tasks=tasks,
        fingerprint=engineering_workflow_plan_fingerprint(
            workflow_id=workflow_id,
            plan_id="plan-1",
            tasks=tasks,
        ),
    )
    dag = FrozenTaskDAG(
        workflow_id=workflow_id,
        plan_fingerprint=plan.fingerprint,
        tasks=tasks,
        fingerprint=task_dag_fingerprint(
            workflow_id=workflow_id,
            plan_fingerprint=plan.fingerprint,
            tasks=tasks,
        ),
    )
    values = dict(
        workflow_id=workflow_id,
        state=WorkflowState.WAITING_APPROVAL,
        requirements=requirements,
        context=context,
        risks=risks,
        plan=plan,
        dag=dag,
        schedule=(),
        progress_sequence=7,
    )
    return FrozenWorkflowSnapshot(
        **values,
        fingerprint=workflow_snapshot_fingerprint(**values),
    )


def human_review_snapshot() -> HumanReviewSnapshot:
    references = ("artifact-1",)
    proposal = ProposalProjection(
        proposal_id="proposal-1",
        artifact_type=ArtifactType.FIRMWARE,
        artifact_version=1,
        summary="Review the generated firmware proposal.",
        reference_ids=references,
        fingerprint=proposal_projection_fingerprint(
            proposal_id="proposal-1",
            artifact_type=ArtifactType.FIRMWARE,
            artifact_version=1,
            summary="Review the generated firmware proposal.",
            reference_ids=references,
        ),
    )
    review = HumanReviewDecisionProjection(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.fingerprint,
        reviewer="engineer-1",
        decision=HumanReviewDecision.APPROVED,
        review_comment="internal review comment must not be projected",
        timestamp=LATER,
        fingerprint=human_review_decision_fingerprint(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.fingerprint,
            reviewer="engineer-1",
            decision=HumanReviewDecision.APPROVED,
            review_comment="internal review comment must not be projected",
            timestamp=LATER,
        ),
    )
    return HumanReviewSnapshot(
        proposal_id=proposal.proposal_id,
        proposal=proposal,
        state=HumanLoopState.COMPLETED,
        review=review,
        progress_sequence=4,
        fingerprint=human_review_snapshot_fingerprint(
            proposal=proposal,
            state=HumanLoopState.COMPLETED,
            review=review,
            progress_sequence=4,
        ),
    )


@pytest.fixture
def workflow_snapshot() -> FrozenWorkflowSnapshot:
    return waiting_workflow_snapshot()


@pytest.fixture
def review_snapshot() -> HumanReviewSnapshot:
    return human_review_snapshot()


@pytest.fixture
def workflow_progress() -> WorkflowProgressEvent:
    return WorkflowProgressEvent(
        sequence=1,
        workflow_id="workflow-1",
        event=WorkflowProgressEventType.WORKFLOW_RECEIVED,
        state=WorkflowState.RECEIVED,
        count=0,
        timestamp=LATER,
    )


@pytest.fixture
def human_progress() -> HumanLoopProgressEvent:
    return HumanLoopProgressEvent(
        sequence=1,
        proposal_id="proposal-1",
        state=HumanLoopState.GENERATED,
        event=HumanLoopProgressEventType.PROPOSAL_GENERATED,
        timestamp=LATER,
    )
