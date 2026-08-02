"""Typed Workflow Runtime to UI projection adapter."""

from __future__ import annotations

from embedded_copilot.workflow_runtime import (
    EngineeringWorkflowPort,
    FrozenWorkflowSnapshot,
    WorkflowPreparationRequest,
    WorkflowProgressEvent,
    WorkflowState,
)

from embedded_copilot.engineering_interface.exceptions import (
    EngineeringWorkflowUnavailable,
)
from embedded_copilot.engineering_interface.models import (
    EngineeringProgressEvent,
    EngineeringProgressSource,
    EngineeringWorkflowPreparationRequest,
    EngineeringWorkflowUIProjection,
    make_progress_event,
    make_workflow_projection,
)

WorkflowPort = EngineeringWorkflowPort


class _WorkflowAdapter:
    def __init__(self, port: EngineeringWorkflowPort) -> None:
        self._port = port

    def prepare(
        self,
        request: EngineeringWorkflowPreparationRequest,
        *,
        requirement_summary: str,
    ) -> EngineeringWorkflowUIProjection:
        workflow_request = WorkflowPreparationRequest(
            workflow_id=request.workflow_id,
            requirement_summary=requirement_summary,
            requested_at=request.requested_at,
        )
        try:
            result = self._port.prepare_workflow(workflow_request)
            if type(result) is not FrozenWorkflowSnapshot:
                raise TypeError("invalid workflow result")
            copied = result.model_copy(deep=True)
            checked = FrozenWorkflowSnapshot.model_validate(copied)
            if checked.workflow_id != request.workflow_id:
                raise ValueError("workflow binding mismatch")
            return make_workflow_projection(
                workflow_id=checked.workflow_id,
                source_message_id=request.source_message_id,
                state=checked.state.value,
                task_count=len(checked.dag.tasks),
                risk_count=len(checked.risks.risks),
                review_required=checked.state is WorkflowState.WAITING_APPROVAL,
                source_snapshot_fingerprint=checked.fingerprint,
            )
        except Exception:
            raise EngineeringWorkflowUnavailable("workflow unavailable") from None


def create_workflow_adapter(port: EngineeringWorkflowPort) -> _WorkflowAdapter:
    if not isinstance(port, EngineeringWorkflowPort):
        raise TypeError("workflow_port must satisfy EngineeringWorkflowPort")
    return _WorkflowAdapter(port)


def project_workflow_progress(
    *,
    session_id: str,
    sequence: int,
    event: object,
) -> EngineeringProgressEvent:
    try:
        if type(event) is not WorkflowProgressEvent:
            raise TypeError("invalid workflow progress")
        copied = event.model_copy(deep=True)
        checked = WorkflowProgressEvent.model_validate(copied)
        return make_progress_event(
            sequence=sequence,
            session_id=session_id,
            source=EngineeringProgressSource.WORKFLOW,
            source_reference_id=checked.workflow_id,
            source_sequence=checked.sequence,
            event=checked.event.value,
            state=checked.state.value,
            count=checked.count,
            timestamp=checked.timestamp,
        )
    except Exception:
        raise EngineeringWorkflowUnavailable("workflow unavailable") from None
