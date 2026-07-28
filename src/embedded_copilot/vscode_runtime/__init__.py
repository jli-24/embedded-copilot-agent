"""Framework-independent VS Code MCP adapter contracts."""

from embedded_copilot.vscode_runtime.errors import VSCodeCapabilityUnavailable
from embedded_copilot.vscode_runtime.facade import VSCodeRuntime
from embedded_copilot.vscode_runtime.models import (
    DEFAULT_CAPABILITIES,
    ChangeProposalResult,
    MCPToolName,
    MCPToolResult,
    VSCodeCapability,
)
from embedded_copilot.vscode_runtime.ports import MCPToolAdapter, VSCodePort
from embedded_copilot.vscode_runtime.runtime import create_vscode_runtime

__all__ = (
    "ChangeProposalResult",
    "DEFAULT_CAPABILITIES",
    "MCPToolAdapter",
    "MCPToolName",
    "MCPToolResult",
    "VSCodeCapability",
    "VSCodeCapabilityUnavailable",
    "VSCodePort",
    "VSCodeRuntime",
    "create_vscode_runtime",
)
