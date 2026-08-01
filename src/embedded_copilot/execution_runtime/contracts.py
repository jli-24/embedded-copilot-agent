"""Protocol boundaries for controlled execution composition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.execution_runtime.approval.context import (
    ExecutionApprovalContext,
)
from embedded_copilot.execution_runtime.models import (
    ExecutionExecutorMetadata,
    ExecutionExecutorResolutionRequest,
    ExecutionInvocationRequest,
    ExecutionPreparationRequest,
    ExecutionProgressEvent,
    ExecutionResultProjection,
    ExecutionSnapshot,
    ExecutionVerificationProjection,
    ExecutionVerificationRequest,
)


@runtime_checkable
class ExecutionPort(Protocol):
    def prepare_execution(
        self, request: ExecutionPreparationRequest
    ) -> ExecutionSnapshot: ...

    def execute(
        self,
        snapshot: ExecutionSnapshot,
        approval: ExecutionApprovalContext,
    ) -> ExecutionSnapshot: ...


@runtime_checkable
class ExecutionExecutorPort(Protocol):
    @property
    def metadata(self) -> ExecutionExecutorMetadata: ...

    def execute(
        self, request: ExecutionInvocationRequest
    ) -> ExecutionResultProjection: ...


@runtime_checkable
class ExecutionExecutorRegistryPort(Protocol):
    def resolve(
        self, request: ExecutionExecutorResolutionRequest
    ) -> ExecutionExecutorPort: ...


@runtime_checkable
class ExecutionVerificationPort(Protocol):
    def verify(
        self, request: ExecutionVerificationRequest
    ) -> ExecutionVerificationProjection: ...


@runtime_checkable
class ExecutionProgressSink(Protocol):
    def emit(self, event: ExecutionProgressEvent) -> None: ...
