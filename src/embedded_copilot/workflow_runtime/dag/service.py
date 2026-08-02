from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.workflow_runtime.exceptions import WorkflowDAGRejected
from embedded_copilot.workflow_runtime.models import (
    EngineeringWorkflowPlan,
    FrozenTaskDAG,
    task_dag_fingerprint,
)


def build_task_dag(plan: EngineeringWorkflowPlan) -> FrozenTaskDAG:
    tasks = tuple(item.model_copy(deep=True) for item in plan.tasks)
    try:
        return FrozenTaskDAG(
            workflow_id=plan.workflow_id,
            plan_fingerprint=plan.fingerprint,
            tasks=tasks,
            fingerprint=task_dag_fingerprint(
                workflow_id=plan.workflow_id,
                plan_fingerprint=plan.fingerprint,
                tasks=tasks,
            ),
        )
    except (TypeError, ValueError, ValidationError):
        raise WorkflowDAGRejected("workflow DAG was rejected") from None
