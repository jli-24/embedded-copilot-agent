from __future__ import annotations

from embedded_copilot.agent_execution import (
    ExecutionContextReference,
    ExecutionContextSourceType,
)
from embedded_copilot.agent_execution.integration import project_workflow_task
from embedded_copilot.workflow_runtime import EngineeringWorkflowTask

from .conftest import NOW


def test_workflow_task_projection_requires_explicit_execution_metadata() -> None:
    task = EngineeringWorkflowTask(
        task_id="task-a",
        summary="Review firmware constraints.",
    )
    references = (
        ExecutionContextReference(
            source_type=ExecutionContextSourceType.WORKFLOW,
            reference_id="reference-1",
        ),
    )

    request = project_workflow_task(
        task,
        execution_id="execution-1",
        workflow_id="workflow-1",
        agent_type="DEBUG",
        context_id="context-1",
        references=references,
        constraints=("Do not execute tools.",),
        timestamp=NOW,
    )

    assert request.agent_type == "DEBUG"
    assert request.input_context.summary == task.summary
    assert request.input_context.references == references
    assert task.task_id == "task-a"


def test_adapter_does_not_infer_agent_type_from_summary() -> None:
    task = EngineeringWorkflowTask(
        task_id="task-a",
        summary="Firmware PCB debug build flash review.",
    )

    request = project_workflow_task(
        task,
        execution_id="execution-1",
        workflow_id="workflow-1",
        agent_type="KNOWLEDGE",
        context_id="context-1",
        references=(),
        constraints=(),
        timestamp=NOW,
    )

    assert request.agent_type == "KNOWLEDGE"
