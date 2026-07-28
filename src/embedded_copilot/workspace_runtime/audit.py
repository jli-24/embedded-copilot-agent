from __future__ import annotations

from embedded_copilot.workspace_runtime.models import (
    ApprovalContext,
    WorkspaceAuditEvent,
)


def applied_audit(
    *,
    proposal_id: str,
    workspace_id: str,
    files: tuple[str, ...],
    approval: ApprovalContext,
) -> WorkspaceAuditEvent:
    return WorkspaceAuditEvent(
        proposal_id=proposal_id,
        workspace_id=workspace_id,
        files=files,
        approved_by=approval.approved_by,
        timestamp=approval.approved_at,
    )
