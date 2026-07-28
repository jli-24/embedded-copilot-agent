"""Transport-neutral MCP tool adapter.

This module does not start a server or implement a transport.
"""

from __future__ import annotations

from collections.abc import Mapping
import json

from pydantic import BaseModel, ValidationError

from embedded_copilot.vscode_runtime.errors import VSCodeCapabilityUnavailable
from embedded_copilot.vscode_runtime.models import (
    DEFAULT_CAPABILITIES,
    MCPToolName,
    MCPToolResult,
    VSCodeCapability,
)
from embedded_copilot.vscode_runtime.ports import MCPToolAdapter, VSCodePort
from embedded_copilot.vscode_runtime.tools import invoke_tool, registered_tools


class _RegisteredMCPToolAdapter:
    __slots__ = ("_port", "_tools")

    def __init__(
        self,
        port: VSCodePort,
        tools: tuple[MCPToolName, ...],
    ) -> None:
        self._port = port
        self._tools = tools

    def list_tools(self) -> tuple[MCPToolName, ...]:
        return self._tools

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, object],
    ) -> MCPToolResult:
        try:
            tool_name = MCPToolName(name)
        except (TypeError, ValueError):
            return _error(None, "unknown_tool")
        if tool_name not in self._tools:
            return _error(tool_name, "capability_denied")
        if not isinstance(arguments, Mapping):
            return _error(tool_name, "invalid_arguments")
        try:
            response = invoke_tool(self._port, tool_name, arguments)
        except ValidationError:
            return _error(tool_name, "invalid_arguments")
        except VSCodeCapabilityUnavailable:
            return _error(tool_name, "capability_denied")
        except Exception:
            return _error(tool_name, "runtime_unavailable")
        if not isinstance(response, BaseModel):
            return _error(tool_name, "runtime_unavailable")
        try:
            payload = json.dumps(
                response.model_dump(mode="json"),
                allow_nan=False,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            return MCPToolResult(
                tool_name=tool_name,
                is_error=False,
                payload_json=payload,
            )
        except Exception:
            return _error(tool_name, "runtime_unavailable")


def _build_mcp_adapter(
    port: VSCodePort,
    *,
    enabled_capabilities: tuple[VSCodeCapability, ...] = DEFAULT_CAPABILITIES,
) -> MCPToolAdapter:
    if not isinstance(port, VSCodePort):
        raise TypeError("vscode port is invalid")
    if not isinstance(enabled_capabilities, tuple):
        raise TypeError("capabilities must be a tuple")
    try:
        capabilities = tuple(
            VSCodeCapability(capability) for capability in enabled_capabilities
        )
    except (TypeError, ValueError):
        raise ValueError("capabilities are invalid") from None
    if len(capabilities) != len(set(capabilities)):
        raise ValueError("capabilities must be unique")
    return _RegisteredMCPToolAdapter(port, registered_tools(capabilities))


def _error(
    tool_name: MCPToolName | None,
    error_code: str,
) -> MCPToolResult:
    return MCPToolResult(
        tool_name=tool_name,
        is_error=True,
        error_code=error_code,
    )
