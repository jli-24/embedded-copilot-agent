from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.workflow_runtime import (
    EngineeringWorkflowPlan,
    EngineeringWorkflowTask,
    WorkflowDAGRejected,
    engineering_workflow_plan_fingerprint,
)
from embedded_copilot.workflow_runtime.dag.service import build_task_dag
from embedded_copilot.workflow_runtime.scheduler.service import build_schedule


def _plan(tasks: tuple[EngineeringWorkflowTask, ...]) -> EngineeringWorkflowPlan:
    return EngineeringWorkflowPlan(
        workflow_id="workflow-1",
        plan_id="plan-invalid",
        tasks=tasks,
        fingerprint=engineering_workflow_plan_fingerprint(
            workflow_id="workflow-1",
            plan_id="plan-invalid",
            tasks=tasks,
        ),
    )


def test_missing_dependency_is_rejected() -> None:
    plan = _plan(
        (
            EngineeringWorkflowTask(
                task_id="task-a",
                summary="Review constraints.",
                dependencies=("missing",),
            ),
        )
    )

    with pytest.raises(WorkflowDAGRejected):
        build_task_dag(plan)


def test_self_edge_is_rejected() -> None:
    plan = _plan(
        (
            EngineeringWorkflowTask(
                task_id="task-a",
                summary="Review constraints.",
                dependencies=("task-a",),
            ),
        )
    )

    with pytest.raises(WorkflowDAGRejected):
        build_task_dag(plan)


def test_duplicate_dependency_is_rejected_by_task_contract() -> None:
    with pytest.raises(ValidationError):
        EngineeringWorkflowTask(
            task_id="task-b",
            summary="Review constraints.",
            dependencies=("task-a", "task-a"),
        )


def test_cycle_is_rejected() -> None:
    plan = _plan(
        (
            EngineeringWorkflowTask(
                task_id="task-a",
                summary="Review requirements.",
                dependencies=("task-b",),
            ),
            EngineeringWorkflowTask(
                task_id="task-b",
                summary="Review constraints.",
                dependencies=("task-a",),
            ),
        )
    )

    with pytest.raises(WorkflowDAGRejected):
        build_task_dag(plan)


def test_topological_batches_are_stable(plan) -> None:
    dag = build_task_dag(plan)

    assert build_schedule(dag) == build_schedule(dag)
    assert tuple(item.task_ids for item in build_schedule(dag)) == (
        ("task-a",),
        ("task-b", "task-c"),
        ("task-d",),
    )
