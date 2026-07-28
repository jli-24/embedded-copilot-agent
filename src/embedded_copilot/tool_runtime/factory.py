from __future__ import annotations

from embedded_copilot.tool_runtime.executor import create_execution_port
from embedded_copilot.tool_runtime.models import _tool_name
from embedded_copilot.tool_runtime.ports import (
    EngineeringToolPort,
    ToolAuditSink,
    ToolPermissionPort,
)
from embedded_copilot.tool_runtime.registry import _ToolRegistry
from embedded_copilot.tool_runtime.runtime import ToolRuntime


def create_tool_runtime(
    *,
    tools: tuple[EngineeringToolPort, ...],
    permission_port: ToolPermissionPort,
    audit_sink: ToolAuditSink,
) -> ToolRuntime:
    if not isinstance(tools, tuple):
        raise TypeError("tools must be a tuple")
    if not tools:
        raise ValueError("tools must not be empty")
    if not isinstance(permission_port, ToolPermissionPort):
        raise TypeError("permission port is invalid")
    if not isinstance(audit_sink, ToolAuditSink):
        raise TypeError("audit sink is invalid")
    names: list[str] = []
    for tool in tools:
        try:
            valid = isinstance(tool, EngineeringToolPort)
        except Exception:
            raise TypeError("engineering tool is invalid") from None
        if not valid:
            raise TypeError("engineering tool is invalid")
        try:
            names.append(_tool_name(tool.tool_name))
        except Exception:
            raise TypeError("engineering tool name is invalid") from None
    if len(names) != len(set(names)):
        raise ValueError("tool names must be unique")
    registry = _ToolRegistry(tuple(zip(names, tools, strict=True)))
    return ToolRuntime._compose(
        create_execution_port(
            registry=registry,
            permission_port=permission_port,
            audit_sink=audit_sink,
        )
    )
