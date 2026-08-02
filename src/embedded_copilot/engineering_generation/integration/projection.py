"""Project public workflow and execution contracts into generation requests."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.agent_execution import (
    AgentExecutionResult,
    AgentExecutionResultStatus,
)
from embedded_copilot.engineering_generation.exceptions import (
    ArtifactGenerationRejected,
)
from embedded_copilot.engineering_generation.models import (
    ArtifactGenerationRequest,
    ArtifactType,
    GenerationContextProjection,
)
from embedded_copilot.workflow_runtime import EngineeringWorkflowTask


def project_generation_request(
    task: EngineeringWorkflowTask,
    execution_result: AgentExecutionResult,
    *,
    generation_id: str,
    artifact_type: ArtifactType,
    input_context: GenerationContextProjection,
    constraints: tuple[str, ...],
    timestamp,
) -> ArtifactGenerationRequest:
    """Create an explicit generation request from verified public envelopes."""
    if (
        type(task) is not EngineeringWorkflowTask
        or type(execution_result) is not AgentExecutionResult
        or type(input_context) is not GenerationContextProjection
    ):
        raise ArtifactGenerationRejected("generation projection is rejected")
    try:
        safe_task = EngineeringWorkflowTask.model_validate(task.model_copy(deep=True))
        safe_result = AgentExecutionResult.model_validate(
            execution_result.model_copy(deep=True)
        )
        safe_context = GenerationContextProjection.model_validate(
            input_context.model_copy(deep=True)
        )
    except (TypeError, ValueError, ValidationError):
        raise ArtifactGenerationRejected("generation projection is rejected") from None
    if (
        safe_result.status is not AgentExecutionResultStatus.SUCCESS
        or safe_result.task_id != safe_task.task_id
    ):
        raise ArtifactGenerationRejected("generation projection is rejected")
    try:
        return ArtifactGenerationRequest(
            generation_id=generation_id,
            workflow_id=safe_result.workflow_id,
            task_id=safe_task.task_id,
            artifact_type=artifact_type,
            input_context=safe_context,
            constraints=constraints,
            timestamp=timestamp,
        )
    except (TypeError, ValueError, ValidationError):
        raise ArtifactGenerationRejected("generation projection is rejected") from None
