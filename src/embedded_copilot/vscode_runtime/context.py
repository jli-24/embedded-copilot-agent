from __future__ import annotations

from embedded_copilot.coding_runtime import (
    BuildAnalysisRequest,
    BuildAnalysisResponse,
    ChangeReview,
    CodingIntelligencePort,
    DiffReviewRequest,
    ProjectAnalysisRequest,
    ProjectAnalysisResponse,
)
from embedded_copilot.vscode_runtime.errors import VSCodeCapabilityUnavailable
from embedded_copilot.vscode_runtime.models import (
    ChangeProposalResult,
    VSCodeCapability,
)
from embedded_copilot.workspace_runtime import (
    ApprovalContext,
    ApplyResult,
    ChangeProposal,
    FrozenWorkspaceSnapshot,
    WorkspaceInspectionRequest,
    WorkspacePort,
)


class _VSCodePort:
    __slots__ = ("_capabilities", "_coding_port", "_workspace_port")

    def __init__(
        self,
        coding_port: CodingIntelligencePort,
        workspace_port: WorkspacePort,
        capabilities: tuple[VSCodeCapability, ...],
    ) -> None:
        self._coding_port = coding_port
        self._workspace_port = workspace_port
        self._capabilities = frozenset(capabilities)

    def inspect_context(
        self, request: WorkspaceInspectionRequest
    ) -> FrozenWorkspaceSnapshot:
        self._require(VSCodeCapability.READ_CONTEXT)
        return self._workspace_port.inspect_workspace(
            WorkspaceInspectionRequest.model_validate(request)
        )

    def analyze_code(self, request: ProjectAnalysisRequest) -> ProjectAnalysisResponse:
        self._require(VSCodeCapability.ANALYZE_CODE)
        return self._coding_port.analyze_project(
            ProjectAnalysisRequest.model_validate(request)
        )

    def analyze_build(self, request: BuildAnalysisRequest) -> BuildAnalysisResponse:
        self._require(VSCodeCapability.ANALYZE_BUILD)
        return self._coding_port.analyze_build(
            BuildAnalysisRequest.model_validate(request)
        )

    def review_diff(self, request: DiffReviewRequest) -> ChangeReview:
        self._require(VSCodeCapability.REVIEW_DIFF)
        return self._coding_port.review_diff(DiffReviewRequest.model_validate(request))

    def create_change_proposal(self, proposal: ChangeProposal) -> ChangeProposalResult:
        self._require(VSCodeCapability.CREATE_PROPOSAL)
        proposal = ChangeProposal.model_validate(proposal)
        return ChangeProposalResult(
            proposal=proposal,
            validation=self._workspace_port.validate_change(proposal),
        )

    def apply_approved_change(
        self, proposal: ChangeProposal, approval: ApprovalContext
    ) -> ApplyResult:
        self._require(VSCodeCapability.APPLY_APPROVED_CHANGE)
        return self._workspace_port.apply_change(
            ChangeProposal.model_validate(proposal),
            ApprovalContext.model_validate(approval),
        )

    def _require(self, capability: VSCodeCapability) -> None:
        if capability not in self._capabilities:
            raise VSCodeCapabilityUnavailable
