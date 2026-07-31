from __future__ import annotations

from embedded_copilot.workflow_runtime.exceptions import WorkflowApprovalRejected
from embedded_copilot.workflow_runtime.models import (
    FrozenWorkflowSnapshot,
    WorkflowApprovalContext,
    WorkflowState,
)


def validate_workflow_approval(
    snapshot: FrozenWorkflowSnapshot,
    approval: WorkflowApprovalContext,
) -> None:
    if snapshot.state is not WorkflowState.WAITING_APPROVAL:
        raise WorkflowApprovalRejected("workflow approval was rejected")
    if (
        approval.workflow_id != snapshot.workflow_id
        or approval.requirement_fingerprint != snapshot.requirements.fingerprint
        or approval.context_fingerprint != snapshot.context.context_fingerprint
        or approval.risk_fingerprint != snapshot.risks.fingerprint
        or approval.dag_fingerprint != snapshot.dag.fingerprint
        or approval.waiting_snapshot_fingerprint != snapshot.fingerprint
    ):
        raise WorkflowApprovalRejected("workflow approval was rejected")
