"""Project a successful Agent Execution result into a safe execution request."""

from __future__ import annotations

from datetime import datetime

from embedded_copilot.agent_execution import (
    AgentExecutionResultStatus,
    AgentExecutionSnapshot,
    AgentExecutionState,
)

from embedded_copilot.execution_runtime.approval.context import ProposalProjection
from embedded_copilot.execution_runtime.exceptions import ExecutionRejected
from embedded_copilot.execution_runtime.models import (
    ExecutionContextProjection,
    ExecutorType,
    ExecutionPreparationRequest,
    ExecutionProposalReference,
    execution_context_fingerprint,
)


def project_agent_execution_snapshot(
    snapshot: AgentExecutionSnapshot,
    *,
    proposal: ProposalProjection,
    execution_id: str,
    executor_type: ExecutorType,
    timestamp: datetime,
) -> ExecutionPreparationRequest:
    """Create a content-free request from typed, successful upstream projections."""
    if (
        type(snapshot) is not AgentExecutionSnapshot
        or type(proposal) is not ProposalProjection
    ):
        raise ExecutionRejected("execution request was rejected")
    try:
        safe_snapshot = AgentExecutionSnapshot.model_validate(
            snapshot.model_copy(deep=True)
        )
        safe_proposal = ProposalProjection.model_validate(
            proposal.model_copy(deep=True)
        )
    except Exception:
        raise ExecutionRejected("execution request was rejected") from None
    if (
        safe_snapshot.state is not AgentExecutionState.SUCCESS
        or safe_snapshot.result_projection is None
        or safe_snapshot.result_projection.status
        is not AgentExecutionResultStatus.SUCCESS
    ):
        raise ExecutionRejected("execution request was rejected")

    references = tuple(
        sorted(
            {
                *(
                    item.reference_id
                    for item in safe_snapshot.request.input_context.references
                ),
                *(
                    item.reference_id
                    for item in safe_snapshot.result_projection.artifacts
                ),
                *safe_proposal.reference_ids,
            }
        )
    )
    summary = safe_snapshot.result_projection.summary
    context = ExecutionContextProjection(
        context_id=safe_snapshot.execution_id,
        summary=summary,
        reference_ids=references,
        fingerprint=execution_context_fingerprint(
            context_id=safe_snapshot.execution_id,
            summary=summary,
            reference_ids=references,
        ),
    )
    return ExecutionPreparationRequest(
        execution_id=execution_id,
        workflow_id=safe_snapshot.workflow_id,
        task_id=safe_snapshot.task_id,
        agent_type=safe_snapshot.agent_type,
        executor_type=executor_type,
        context=context,
        proposal=ExecutionProposalReference(
            proposal_id=safe_proposal.proposal_id,
            proposal_fingerprint=safe_proposal.fingerprint,
        ),
        timestamp=timestamp,
    )


__all__ = ("project_agent_execution_snapshot",)
