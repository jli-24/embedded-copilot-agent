from __future__ import annotations

import pytest

from embedded_copilot.agent_execution import (
    AgentExecutionResultStatus,
)
from embedded_copilot.engineering_generation import (
    ArtifactGenerationRejected,
    ArtifactType,
    GenerationContextProjection,
)
from embedded_copilot.engineering_generation.integration import (
    project_generation_request,
)
from embedded_copilot.workflow_runtime import EngineeringWorkflowTask
from tests.agent_execution.conftest import request_for as execution_request_for
from tests.agent_execution.conftest import result_for

from .conftest import NOW


def test_workflow_and_execution_projection_is_explicit() -> None:
    execution_request = execution_request_for(agent_type="FIRMWARE")
    execution_result = result_for(execution_request)
    task = EngineeringWorkflowTask(
        task_id=execution_result.task_id,
        summary="Prepare a firmware proposal.",
    )
    context = GenerationContextProjection(
        summary="Safe context.",
        references=(),
        verified_source_references=(),
    )

    projected = project_generation_request(
        task,
        execution_result,
        generation_id="generation-1",
        artifact_type=ArtifactType.FIRMWARE,
        input_context=context,
        constraints=("Do not modify files.",),
        timestamp=NOW,
    )

    assert projected.artifact_type is ArtifactType.FIRMWARE
    assert projected.task_id == task.task_id
    assert projected.workflow_id == execution_result.workflow_id
    assert projected.input_context is not context


def test_failed_execution_cannot_project_generation_request() -> None:
    execution_request = execution_request_for()
    execution_result = result_for(
        execution_request,
        status=AgentExecutionResultStatus.FAILED,
    )
    task = EngineeringWorkflowTask(
        task_id=execution_result.task_id,
        summary="Prepare proposal.",
    )

    with pytest.raises(ArtifactGenerationRejected):
        project_generation_request(
            task,
            execution_result,
            generation_id="generation-1",
            artifact_type=ArtifactType.HARDWARE_DESIGN,
            input_context=GenerationContextProjection(
                summary="Safe context.", references=(), verified_source_references=()
            ),
            constraints=(),
            timestamp=NOW,
        )
