"""Protocol boundaries for Optimization Runtime composition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.optimization.approval.context import (
    OptimizationApprovalContext,
)
from embedded_copilot.optimization.models import (
    OptimizationAlgorithmMetadata,
    OptimizationEvaluationProjection,
    OptimizationEvaluationRequest,
    OptimizationInvocationRequest,
    OptimizationProgressEvent,
    OptimizationProposal,
    OptimizationRequest,
    OptimizationResolutionRequest,
    OptimizationSnapshot,
)


@runtime_checkable
class OptimizationPort(Protocol):
    def create_plan(self, request: OptimizationRequest) -> OptimizationSnapshot: ...

    def evaluate(self, snapshot: OptimizationSnapshot) -> OptimizationSnapshot: ...

    def approve(
        self,
        snapshot: OptimizationSnapshot,
        approval: OptimizationApprovalContext,
    ) -> OptimizationSnapshot: ...


@runtime_checkable
class OptimizationAlgorithmPort(Protocol):
    @property
    def metadata(self) -> OptimizationAlgorithmMetadata: ...

    def propose(
        self, request: OptimizationInvocationRequest
    ) -> OptimizationProposal: ...


@runtime_checkable
class OptimizationRegistryPort(Protocol):
    def resolve(
        self, request: OptimizationResolutionRequest
    ) -> OptimizationAlgorithmPort: ...


@runtime_checkable
class OptimizationEvaluationPort(Protocol):
    def evaluate(
        self, request: OptimizationEvaluationRequest
    ) -> OptimizationEvaluationProjection: ...


@runtime_checkable
class OptimizationProgressSink(Protocol):
    def emit(self, event: OptimizationProgressEvent) -> None: ...
