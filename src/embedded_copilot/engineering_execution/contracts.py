"""Public Port boundaries for Engineering Execution."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_execution.integration.inputs import (
    EngineeringExecutionRequest,
)
from embedded_copilot.engineering_execution.models import (
    BuildRequest,
    BuildResult,
    DebugRequest,
    DebugResult,
    EngineeringExecutionReport,
    ExecutionAdapterMetadata,
    FlashRequest,
    FlashResult,
)


@runtime_checkable
class EngineeringExecutionPort(Protocol):
    def execute(
        self,
        request: EngineeringExecutionRequest,
    ) -> EngineeringExecutionReport: ...


@runtime_checkable
class BuildPort(Protocol):
    @property
    def metadata(self) -> ExecutionAdapterMetadata: ...

    def build(self, request: BuildRequest) -> BuildResult: ...


@runtime_checkable
class FlashPort(Protocol):
    @property
    def metadata(self) -> ExecutionAdapterMetadata: ...

    def flash(self, request: FlashRequest) -> FlashResult: ...


@runtime_checkable
class DebugPort(Protocol):
    @property
    def metadata(self) -> ExecutionAdapterMetadata: ...

    def debug(self, request: DebugRequest) -> DebugResult: ...
