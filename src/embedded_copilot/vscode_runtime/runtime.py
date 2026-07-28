from __future__ import annotations

from embedded_copilot.coding_runtime import CodingIntelligencePort
from embedded_copilot.vscode_runtime.context import _VSCodePort
from embedded_copilot.vscode_runtime.facade import VSCodeRuntime
from embedded_copilot.vscode_runtime.models import (
    DEFAULT_CAPABILITIES,
    VSCodeCapability,
)
from embedded_copilot.workspace_runtime import WorkspacePort


def create_vscode_runtime(
    *,
    coding_port: CodingIntelligencePort,
    workspace_port: WorkspacePort,
    enabled_capabilities: tuple[VSCodeCapability, ...] = DEFAULT_CAPABILITIES,
) -> VSCodeRuntime:
    if not isinstance(coding_port, CodingIntelligencePort):
        raise TypeError("coding port is invalid")
    if not isinstance(workspace_port, WorkspacePort):
        raise TypeError("workspace port is invalid")
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
    return VSCodeRuntime._compose(
        _VSCodePort(coding_port, workspace_port, capabilities)
    )
