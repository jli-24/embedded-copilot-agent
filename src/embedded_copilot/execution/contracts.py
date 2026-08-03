"""Ports for controlled build delegation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.execution.models import (
    BuildExecutionRequest,
    BuildResult,
    ESPIdfBuildInvocation,
    HostBuildResult,
)


@runtime_checkable
class ESPIdfBuildExecutionPort(Protocol):
    async def build(self, request: ESPIdfBuildInvocation) -> HostBuildResult: ...


@runtime_checkable
class BuildExecutionServicePort(Protocol):
    async def execute(self, request: BuildExecutionRequest) -> BuildResult: ...
