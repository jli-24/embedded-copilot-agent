from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.workflow_runtime import (
    EngineeringWorkflowPlan,
    EngineeringWorkflowTask,
    RequirementSpecification,
    VerifiedWorkflowSourceReference,
    WorkflowApprovalContext,
    WorkflowApprovalDecision,
    WorkflowContextProjection,
    WorkflowRiskItem,
    WorkflowSourceType,
    engineering_workflow_plan_fingerprint,
    requirement_specification_fingerprint,
    workflow_context_fingerprint,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 8, 1, 13, 0, tzinfo=UTC)


@pytest.fixture
def requirements() -> RequirementSpecification:
    values = ("Define MCU constraints.", "Verify interface compatibility.")
    constraints = ("Do not execute engineering tasks.",)
    assumptions = ("Verified context is caller supplied.",)
    return RequirementSpecification(
        workflow_id="workflow-1",
        requirements=values,
        constraints=constraints,
        assumptions=assumptions,
        fingerprint=requirement_specification_fingerprint(
            workflow_id="workflow-1",
            requirements=values,
            constraints=constraints,
            assumptions=assumptions,
        ),
    )


def context_for(
    requirements: RequirementSpecification,
    *,
    risks: tuple[WorkflowRiskItem, ...] | None = None,
) -> WorkflowContextProjection:
    sources = (
        VerifiedWorkflowSourceReference(
            source_type=WorkflowSourceType.KNOWLEDGE_CONTEXT,
            source_id="knowledge-1",
            reference="https://example.invalid/datasheet",
            confidence=1.0,
        ),
        VerifiedWorkflowSourceReference(
            source_type=WorkflowSourceType.MEMORY_CONTEXT,
            source_id="memory-1",
            reference="memory-known-issue-1",
            confidence=0.8,
        ),
    )
    projected = risks
    if projected is None:
        projected = (
            WorkflowRiskItem(
                risk_type="GPIO_CONFLICT",
                source_type=WorkflowSourceType.KNOWLEDGE_CONTEXT,
                source_id="knowledge-1",
                confidence=1.0,
                reference="https://example.invalid/datasheet",
            ),
        )
    return WorkflowContextProjection(
        workflow_id=requirements.workflow_id,
        requirement_fingerprint=requirements.fingerprint,
        context_fingerprint=workflow_context_fingerprint(
            workflow_id=requirements.workflow_id,
            requirement_fingerprint=requirements.fingerprint,
            confidence=0.8,
            verified_source_references=sources,
        ),
        confidence=0.8,
        verified_source_references=sources,
        projected_risks=projected,
    )


@pytest.fixture
def context(requirements: RequirementSpecification) -> WorkflowContextProjection:
    return context_for(requirements)


@pytest.fixture
def plan() -> EngineeringWorkflowPlan:
    tasks = (
        EngineeringWorkflowTask(
            task_id="task-a",
            summary="Review requirements.",
        ),
        EngineeringWorkflowTask(
            task_id="task-b",
            summary="Review MCU constraints.",
            dependencies=("task-a",),
        ),
        EngineeringWorkflowTask(
            task_id="task-c",
            summary="Review interface constraints.",
            dependencies=("task-a",),
        ),
        EngineeringWorkflowTask(
            task_id="task-d",
            summary="Prepare verification review.",
            dependencies=("task-b", "task-c"),
        ),
    )
    return EngineeringWorkflowPlan(
        workflow_id="workflow-1",
        plan_id="plan-1",
        tasks=tasks,
        fingerprint=engineering_workflow_plan_fingerprint(
            workflow_id="workflow-1",
            plan_id="plan-1",
            tasks=tasks,
        ),
    )


def approval_for(snapshot, *, decision=WorkflowApprovalDecision.APPROVED):
    return WorkflowApprovalContext(
        workflow_id=snapshot.workflow_id,
        requirement_fingerprint=snapshot.requirements.fingerprint,
        context_fingerprint=snapshot.context.context_fingerprint,
        risk_fingerprint=snapshot.risks.fingerprint,
        dag_fingerprint=snapshot.dag.fingerprint,
        waiting_snapshot_fingerprint=snapshot.fingerprint,
        decision=decision,
        reviewer="engineer-1",
        reviewed_at=REVIEWED_AT,
    )
