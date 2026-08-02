from __future__ import annotations

from embedded_copilot.workflow_runtime.models import (
    FrozenTaskDAG,
    WorkflowScheduleBatch,
)


def build_schedule(dag: FrozenTaskDAG) -> tuple[WorkflowScheduleBatch, ...]:
    """Project deterministic topological batches from a validated DAG."""
    remaining = {item.task_id: set(item.dependencies) for item in dag.tasks}
    batches: list[WorkflowScheduleBatch] = []
    while remaining:
        ready = tuple(
            sorted(
                task_id
                for task_id, dependencies in remaining.items()
                if not dependencies
            )
        )
        batches.append(
            WorkflowScheduleBatch(
                batch_index=len(batches) + 1,
                task_ids=ready,
            )
        )
        for task_id in ready:
            remaining.pop(task_id)
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return tuple(batches)
