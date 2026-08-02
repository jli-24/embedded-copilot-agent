from __future__ import annotations

from copy import deepcopy

import pytest

from embedded_copilot.engineering_interface import (
    EngineeringChatRequest,
    EngineeringChatRole,
    EngineeringInterfaceRejected,
    EngineeringProjectProjection,
    EngineeringSessionCreateRequest,
    EngineeringWorkflowPreparationRequest,
    EngineeringWorkflowUnavailable,
    create_engineering_interface_runtime,
    engineering_project_fingerprint,
)

from .conftest import LATER, NOW


class WorkflowPort:
    def __init__(self, result, *, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.prepare_calls = []
        self.schedule_calls = []

    def prepare_workflow(self, request):
        self.prepare_calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result

    def schedule_workflow(self, snapshot, approval):
        self.schedule_calls.append((snapshot, approval))
        raise AssertionError("schedule_workflow must not be called")


def _session(port):
    project = EngineeringProjectProjection(
        project_id="project-1",
        name="ESP32-S3 Smart Camera",
        summary="A safe project summary.",
        reference_ids=(),
        fingerprint=engineering_project_fingerprint(
            project_id="project-1",
            name="ESP32-S3 Smart Camera",
            summary="A safe project summary.",
            reference_ids=(),
        ),
    )
    session = port.create_session(
        EngineeringSessionCreateRequest(
            session_id="session-1",
            title="Design discussion 1",
            project=project,
            created_at=NOW,
        )
    )
    return port.submit_message(
        session,
        EngineeringChatRequest(
            session_id="session-1",
            message_id="message-1",
            role=EngineeringChatRole.USER,
            summary="Review the ESP32-S3 camera design.",
            reference_ids=(),
            timestamp=LATER,
        ),
    )


def test_workflow_preparation_is_explicit_safe_and_single_call(
    workflow_snapshot,
) -> None:
    dependency = WorkflowPort(workflow_snapshot)
    port = create_engineering_interface_runtime(
        workflow_port=dependency
    ).engineering_interface_port()
    session = _session(port)
    before = deepcopy(session.model_dump(mode="json"))
    request = EngineeringWorkflowPreparationRequest(
        session_id="session-1",
        workflow_id="workflow-1",
        source_message_id="message-1",
        requested_at=LATER,
    )

    result = port.prepare_workflow(session, request)

    assert session.model_dump(mode="json") == before
    assert len(dependency.prepare_calls) == 1
    assert (
        dependency.prepare_calls[0].requirement_summary == session.messages[0].summary
    )
    assert dependency.schedule_calls == []
    assert result.workflows[0].task_count == 1
    assert result.workflows[0].risk_count == 0
    assert result.workflows[0].review_required is True
    serialized = result.model_dump_json()
    for forbidden in ("requirements", "verified_source_references", "dag", "schedule"):
        assert forbidden not in serialized


def test_workflow_failure_is_sanitized_and_session_is_unchanged(
    workflow_snapshot,
) -> None:
    dependency = WorkflowPort(
        workflow_snapshot,
        error=RuntimeError("C:\\secret\\database.db provider payload"),
    )
    port = create_engineering_interface_runtime(
        workflow_port=dependency
    ).engineering_interface_port()
    session = _session(port)
    before = session.model_dump(mode="json")
    request = EngineeringWorkflowPreparationRequest(
        session_id="session-1",
        workflow_id="workflow-1",
        source_message_id="message-1",
        requested_at=LATER,
    )
    with pytest.raises(EngineeringWorkflowUnavailable) as captured:
        port.prepare_workflow(session, request)
    assert str(captured.value) == "workflow unavailable"
    assert session.model_dump(mode="json") == before
    assert len(dependency.prepare_calls) == 1


def test_progress_and_human_review_are_safe_typed_projections(
    workflow_snapshot,
    workflow_progress,
    human_progress,
    review_snapshot,
) -> None:
    dependency = WorkflowPort(workflow_snapshot)
    port = create_engineering_interface_runtime(
        workflow_port=dependency
    ).engineering_interface_port()
    session = _session(port)
    workflow_state = port.project_workflow_progress(session, workflow_progress)
    human_state = port.project_human_loop_progress(workflow_state, human_progress)
    result = port.project_human_review(human_state, review_snapshot)

    assert tuple(event.sequence for event in result.progress_events) == tuple(
        range(1, len(result.progress_events) + 1)
    )
    assert result.progress_events[-2].source_sequence == 1
    assert result.progress_events[-1].event == "HUMAN_REVIEW_PROJECTED"
    assert result.human_reviews[0].proposal_id == "proposal-1"
    serialized = result.model_dump_json().casefold()
    for forbidden in (
        "internal review comment",
        "review_comment",
        "feedback",
        "revision",
        "approval body",
    ):
        assert forbidden not in serialized


def test_progress_rejects_duplicate_or_out_of_order_events(
    workflow_snapshot,
    workflow_progress,
) -> None:
    port = create_engineering_interface_runtime(
        workflow_port=WorkflowPort(workflow_snapshot)
    ).engineering_interface_port()
    session = _session(port)
    updated = port.project_workflow_progress(session, workflow_progress)
    with pytest.raises(EngineeringInterfaceRejected):
        port.project_workflow_progress(updated, workflow_progress)
