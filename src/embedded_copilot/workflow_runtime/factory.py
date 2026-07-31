from __future__ import annotations

from embedded_copilot.workflow_runtime.contracts import (
    EngineeringPlanningAgentPort,
    RequirementAgentPort,
    WorkflowContextPort,
    WorkflowProgressSink,
)
from embedded_copilot.workflow_runtime.facade import WorkflowRuntime
from embedded_copilot.workflow_runtime.runtime import _create_workflow_service


def create_workflow_runtime(
    *,
    requirement_agent: RequirementAgentPort,
    planning_agent: EngineeringPlanningAgentPort,
    context_port: WorkflowContextPort,
    progress_sink: WorkflowProgressSink,
) -> WorkflowRuntime:
    boundaries = (
        (requirement_agent, RequirementAgentPort, "requirement agent"),
        (planning_agent, EngineeringPlanningAgentPort, "planning agent"),
        (context_port, WorkflowContextPort, "context port"),
        (progress_sink, WorkflowProgressSink, "progress sink"),
    )
    for value, contract, name in boundaries:
        try:
            valid = isinstance(value, contract)
        except Exception:
            raise TypeError(f"{name} is invalid") from None
        if not valid:
            raise TypeError(f"{name} is invalid")
    return WorkflowRuntime._compose(
        _create_workflow_service(
            requirement_agent=requirement_agent,
            planning_agent=planning_agent,
            context_port=context_port,
            progress_sink=progress_sink,
        )
    )
