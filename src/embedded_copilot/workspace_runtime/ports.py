from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.workspace_runtime.models import (
    ApprovalContext,
    ApplyResult,
    ChangeProposal,
    FrozenWorkspaceSnapshot,
    ValidationResult,
    WorkspaceInspectionRequest,
)


@runtime_checkable
class WorkspacePort(Protocol):
    def inspect_workspace(
        self, request: WorkspaceInspectionRequest
    ) -> FrozenWorkspaceSnapshot: ...

    def validate_change(self, proposal: ChangeProposal) -> ValidationResult: ...

    def apply_change(
        self, proposal: ChangeProposal, approval: ApprovalContext
    ) -> ApplyResult: ...
