from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from embedded_copilot.coding_runtime import (
    BuildAnalysisRequest,
    BuildAnalysisResponse,
    ChangeReview,
    DiffReviewRequest,
    ProjectAnalysisRequest,
    ProjectAnalysisResponse,
)
from embedded_copilot.vscode_runtime.models import (
    ChangeProposalResult,
    MCPToolName,
    MCPToolResult,
)
from embedded_copilot.workspace_runtime import (
    ApprovalContext,
    ApplyResult,
    ChangeProposal,
    FrozenWorkspaceSnapshot,
    WorkspaceInspectionRequest,
)


@runtime_checkable
class VSCodePort(Protocol):
    def inspect_context(
        self, request: WorkspaceInspectionRequest
    ) -> FrozenWorkspaceSnapshot: ...

    def analyze_code(
        self, request: ProjectAnalysisRequest
    ) -> ProjectAnalysisResponse: ...

    def analyze_build(self, request: BuildAnalysisRequest) -> BuildAnalysisResponse: ...

    def review_diff(self, request: DiffReviewRequest) -> ChangeReview: ...

    def create_change_proposal(
        self, proposal: ChangeProposal
    ) -> ChangeProposalResult: ...

    def apply_approved_change(
        self, proposal: ChangeProposal, approval: ApprovalContext
    ) -> ApplyResult: ...


@runtime_checkable
class MCPToolAdapter(Protocol):
    def list_tools(self) -> tuple[MCPToolName, ...]: ...

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, object],
    ) -> MCPToolResult: ...
