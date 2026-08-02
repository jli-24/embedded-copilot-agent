"""Public Protocol boundaries for agent execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from embedded_copilot.agent_execution.models import (
    AgentBindingMetadata,
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentExecutionSnapshot,
    AgentInvocationRequest,
    AgentResolutionRequest,
    ExecutionApprovalContext,
    ExecutionProgressEvent,
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
)


@runtime_checkable
class AgentExecutionBoundaryPort(Protocol):
    def execute(self, request: AgentInvocationRequest) -> AgentExecutionResult: ...


@dataclass(frozen=True, slots=True)
class AgentCapabilityBinding:
    metadata: AgentBindingMetadata
    execution_port: AgentExecutionBoundaryPort


@runtime_checkable
class AgentRegistryPort(Protocol):
    def resolve(self, request: AgentResolutionRequest) -> AgentCapabilityBinding: ...


@runtime_checkable
class ExecutionVerificationPort(Protocol):
    def verify(
        self, request: ExecutionVerificationRequest
    ) -> ExecutionVerificationResult: ...


@runtime_checkable
class ExecutionProgressSink(Protocol):
    def emit(self, event: ExecutionProgressEvent) -> None: ...


@runtime_checkable
class AgentExecutionPort(Protocol):
    def execute_task(
        self, request: AgentExecutionRequest
    ) -> AgentExecutionSnapshot: ...

    def resume_execution(
        self,
        snapshot: AgentExecutionSnapshot,
        approval: ExecutionApprovalContext,
    ) -> AgentExecutionSnapshot: ...
