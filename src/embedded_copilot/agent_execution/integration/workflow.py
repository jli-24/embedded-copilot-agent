"""Explicit projection from the public Workflow Runtime task contract."""

from __future__ import annotations

from datetime import datetime

from embedded_copilot.agent_execution import (
    AgentExecutionRejected,
    AgentExecutionInputContext,
    AgentExecutionRequest,
    ExecutionContextReference,
)
from embedded_copilot.workflow_runtime import EngineeringWorkflowTask


def project_workflow_task(
    task: EngineeringWorkflowTask,
    *,
    execution_id: str,
    workflow_id: str,
    agent_type: str,
    context_id: str,
    references: tuple[ExecutionContextReference, ...],
    constraints: tuple[str, ...],
    timestamp: datetime,
) -> AgentExecutionRequest:
    """Project an explicit workflow task without inferring execution metadata."""
    if type(task) is not EngineeringWorkflowTask:
        raise AgentExecutionRejected("workflow task is invalid")
    try:
        safe_task = EngineeringWorkflowTask.model_validate(task.model_copy(deep=True))
    except (TypeError, ValueError):
        raise AgentExecutionRejected("workflow task is invalid") from None
    return AgentExecutionRequest(
        execution_id=execution_id,
        workflow_id=workflow_id,
        task_id=safe_task.task_id,
        agent_type=agent_type,
        input_context=AgentExecutionInputContext(
            context_id=context_id,
            summary=safe_task.summary,
            references=references,
        ),
        constraints=constraints,
        timestamp=timestamp,
    )
