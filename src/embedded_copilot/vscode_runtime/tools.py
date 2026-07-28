from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from embedded_copilot.coding_runtime import (
    BuildAnalysisRequest,
    DiffReviewRequest,
    ProjectAnalysisRequest,
)
from embedded_copilot.vscode_runtime.models import (
    ApprovedChangeRequest,
    MCPToolName,
    VSCodeCapability,
)
from embedded_copilot.vscode_runtime.ports import VSCodePort
from embedded_copilot.workspace_runtime import (
    ChangeProposal,
    WorkspaceInspectionRequest,
)

_TOOL_CAPABILITIES: tuple[tuple[MCPToolName, VSCodeCapability], ...] = (
    (MCPToolName.INSPECT_WORKSPACE_CONTEXT, VSCodeCapability.READ_CONTEXT),
    (MCPToolName.ANALYZE_CODE, VSCodeCapability.ANALYZE_CODE),
    (MCPToolName.ANALYZE_BUILD_LOG, VSCodeCapability.ANALYZE_BUILD),
    (MCPToolName.REVIEW_DIFF, VSCodeCapability.REVIEW_DIFF),
    (MCPToolName.CREATE_CHANGE_PROPOSAL, VSCodeCapability.CREATE_PROPOSAL),
    (
        MCPToolName.APPLY_APPROVED_CHANGE,
        VSCodeCapability.APPLY_APPROVED_CHANGE,
    ),
)


def registered_tools(
    capabilities: tuple[VSCodeCapability, ...],
) -> tuple[MCPToolName, ...]:
    enabled = frozenset(capabilities)
    return tuple(
        tool_name
        for tool_name, capability in _TOOL_CAPABILITIES
        if capability in enabled
    )


def invoke_tool(
    port: VSCodePort,
    tool_name: MCPToolName,
    arguments: Mapping[str, object],
) -> BaseModel:
    if tool_name is MCPToolName.INSPECT_WORKSPACE_CONTEXT:
        return port.inspect_context(
            WorkspaceInspectionRequest.model_validate(arguments)
        )
    if tool_name is MCPToolName.ANALYZE_CODE:
        return port.analyze_code(ProjectAnalysisRequest.model_validate(arguments))
    if tool_name is MCPToolName.ANALYZE_BUILD_LOG:
        return port.analyze_build(BuildAnalysisRequest.model_validate(arguments))
    if tool_name is MCPToolName.REVIEW_DIFF:
        return port.review_diff(DiffReviewRequest.model_validate(arguments))
    if tool_name is MCPToolName.CREATE_CHANGE_PROPOSAL:
        return port.create_change_proposal(ChangeProposal.model_validate(arguments))
    approved = ApprovedChangeRequest.model_validate(arguments)
    return port.apply_approved_change(approved.proposal, approved.approval)
