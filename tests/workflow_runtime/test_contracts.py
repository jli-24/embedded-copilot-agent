from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.workflow_runtime import (
    EngineeringWorkflowPlan,
    EngineeringWorkflowTask,
    RequirementSpecification,
    WorkflowPreparationRequest,
    WorkflowRiskItem,
    WorkflowSourceType,
    engineering_workflow_plan_fingerprint,
    requirement_specification_fingerprint,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def test_workflow_contracts_are_strict_frozen_and_forbid_extra_fields() -> None:
    request = WorkflowPreparationRequest(
        workflow_id="workflow-1",
        requirement_summary="Review the embedded design requirements.",
        requested_at=NOW,
    )

    with pytest.raises(ValidationError):
        request.workflow_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        WorkflowPreparationRequest.model_validate(
            {
                **request.model_dump(mode="python"),
                "risk": "GPIO_CONFLICT",
            }
        )


def test_naive_timestamp_and_list_collection_are_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowPreparationRequest(
            workflow_id="workflow-1",
            requirement_summary="Review requirements.",
            requested_at=datetime(2026, 8, 1, 12, 0),
        )
    with pytest.raises(ValidationError):
        RequirementSpecification(
            workflow_id="workflow-1",
            requirements=["Review requirements."],
            constraints=(),
            assumptions=(),
            fingerprint="sha256:" + "0" * 64,
        )


@pytest.mark.parametrize(
    "risk_type",
    ("possible issue", "AI_THINKS_PCB_BAD!", "AB", "maybe_unstable"),
)
def test_risk_type_rejects_reasoning_text(risk_type: str) -> None:
    with pytest.raises(ValidationError):
        WorkflowRiskItem(
            risk_type=risk_type,
            source_type=WorkflowSourceType.KNOWLEDGE_CONTEXT,
            source_id="source-1",
            confidence=1.0,
            reference="https://example.invalid/reference",
        )


def test_risk_contract_rejects_payload_fields() -> None:
    with pytest.raises(ValidationError):
        WorkflowRiskItem.model_validate(
            {
                "risk_type": "GPIO_CONFLICT",
                "source_type": WorkflowSourceType.KNOWLEDGE_CONTEXT,
                "source_id": "source-1",
                "confidence": 1.0,
                "reference": "https://example.invalid/reference",
                "payload": "raw evidence",
            }
        )


def test_plan_rejects_more_than_128_tasks() -> None:
    tasks = tuple(
        EngineeringWorkflowTask(
            task_id=f"task-{index:03d}",
            summary=f"Review task {index}.",
        )
        for index in range(129)
    )
    with pytest.raises(ValidationError):
        EngineeringWorkflowPlan(
            workflow_id="workflow-1",
            plan_id="plan-1",
            tasks=tasks,
            fingerprint=engineering_workflow_plan_fingerprint(
                workflow_id="workflow-1",
                plan_id="plan-1",
                tasks=tasks,
            ),
        )


def test_requirement_fingerprint_is_stable() -> None:
    fingerprint = requirement_specification_fingerprint(
        workflow_id="workflow-1",
        requirements=("Review requirements.",),
        constraints=(),
        assumptions=(),
    )
    assert fingerprint == requirement_specification_fingerprint(
        workflow_id="workflow-1",
        requirements=("Review requirements.",),
        constraints=(),
        assumptions=(),
    )
