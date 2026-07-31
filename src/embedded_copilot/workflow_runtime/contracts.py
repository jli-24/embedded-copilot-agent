from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.workflow_runtime.models import (
    EngineeringPlanningRequest,
    EngineeringWorkflowPlan,
    FrozenWorkflowSnapshot,
    RequirementAgentRequest,
    RequirementSpecification,
    WorkflowApprovalContext,
    WorkflowContextProjection,
    WorkflowContextRequest,
    WorkflowPreparationRequest,
    WorkflowProgressEvent,
)


@runtime_checkable
class RequirementAgentPort(Protocol):
    def analyze(self, request: RequirementAgentRequest) -> RequirementSpecification: ...


@runtime_checkable
class WorkflowContextPort(Protocol):
    """External composition boundary for verified context projections."""

    def resolve(self, request: WorkflowContextRequest) -> WorkflowContextProjection: ...


@runtime_checkable
class EngineeringPlanningAgentPort(Protocol):
    def plan(self, request: EngineeringPlanningRequest) -> EngineeringWorkflowPlan: ...


@runtime_checkable
class WorkflowProgressSink(Protocol):
    def emit(self, event: WorkflowProgressEvent) -> None: ...


@runtime_checkable
class EngineeringWorkflowPort(Protocol):
    def prepare_workflow(
        self,
        request: WorkflowPreparationRequest,
    ) -> FrozenWorkflowSnapshot: ...

    def schedule_workflow(
        self,
        snapshot: FrozenWorkflowSnapshot,
        approval: WorkflowApprovalContext,
    ) -> FrozenWorkflowSnapshot: ...
