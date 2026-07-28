from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.tool_runtime.models import (
    ToolAdapterResult,
    ToolAuditEvent,
    ToolExecutionContext,
    ToolPermissionDecision,
    ToolResult,
)


@runtime_checkable
class ToolExecutionPort(Protocol):
    def execute(self, context: ToolExecutionContext) -> ToolResult: ...


@runtime_checkable
class EngineeringToolPort(Protocol):
    @property
    def tool_name(self) -> str: ...

    def execute(self, context: ToolExecutionContext) -> ToolAdapterResult: ...


@runtime_checkable
class ToolPermissionPort(Protocol):
    def authorize(self, context: ToolExecutionContext) -> ToolPermissionDecision: ...


@runtime_checkable
class ToolAuditSink(Protocol):
    def record(self, event: ToolAuditEvent) -> None: ...
