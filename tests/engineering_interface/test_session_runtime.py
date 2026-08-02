from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_interface import (
    AttachmentProjectionRequest,
    AttachmentProjectionType,
    EngineeringChatRequest,
    EngineeringChatRole,
    EngineeringInterfaceRejected,
    EngineeringProjectProjection,
    EngineeringSessionCreateRequest,
    create_engineering_interface_runtime,
    engineering_project_fingerprint,
)

from .conftest import LATER, NOW


class WorkflowPort:
    def __init__(self, result) -> None:
        self.result = result
        self.prepare_calls = []
        self.schedule_calls = []

    def prepare_workflow(self, request):
        self.prepare_calls.append(request)
        return self.result

    def schedule_workflow(self, snapshot, approval):
        self.schedule_calls.append((snapshot, approval))
        raise AssertionError("schedule_workflow must not be called")


def _project() -> EngineeringProjectProjection:
    references = ("project-ref-1",)
    return EngineeringProjectProjection(
        project_id="project-1",
        name="ESP32-S3 Smart Camera",
        summary="A safe project summary.",
        reference_ids=references,
        fingerprint=engineering_project_fingerprint(
            project_id="project-1",
            name="ESP32-S3 Smart Camera",
            summary="A safe project summary.",
            reference_ids=references,
        ),
    )


def _runtime(workflow_snapshot):
    dependency = WorkflowPort(workflow_snapshot)
    runtime = create_engineering_interface_runtime(workflow_port=dependency)
    return runtime.engineering_interface_port(), dependency


def _session(port):
    return port.create_session(
        EngineeringSessionCreateRequest(
            session_id="session-1",
            title="Design discussion 1",
            project=_project(),
            created_at=NOW,
        )
    )


def test_project_can_be_shared_by_multiple_caller_owned_sessions(
    workflow_snapshot,
) -> None:
    port, _ = _runtime(workflow_snapshot)
    project = _project()
    first_request = EngineeringSessionCreateRequest(
        session_id="session-1",
        title="Design discussion 1",
        project=project,
        created_at=NOW,
    )
    second_request = EngineeringSessionCreateRequest(
        session_id="session-2",
        title="Design discussion 2",
        project=project,
        created_at=NOW,
    )

    first = port.create_session(first_request)
    second = port.create_session(second_request)

    assert first.project == second.project == project
    assert first.project is not project
    assert second.project is not project
    assert first.session_id != second.session_id


def test_chat_and_attachment_are_metadata_only_and_inputs_are_immutable(
    workflow_snapshot,
) -> None:
    port, _ = _runtime(workflow_snapshot)
    original = _session(port)
    original_dump = deepcopy(original.model_dump(mode="json"))
    attachment = AttachmentProjectionRequest(
        session_id="session-1",
        reference_id="image-1",
        type=AttachmentProjectionType.IMAGE,
        basename="camera-board.png",
        summary="Board image reference metadata.",
        size_bytes=1024,
        timestamp=LATER,
    )
    with_attachment = port.project_attachment(original, attachment)
    message = EngineeringChatRequest(
        session_id="session-1",
        message_id="message-1",
        role=EngineeringChatRole.USER,
        summary="Review the ESP32-S3 camera design.",
        reference_ids=("image-1",),
        timestamp=LATER,
    )
    result = port.submit_message(with_attachment, message)

    assert original.model_dump(mode="json") == original_dump
    assert result is not with_attachment
    assert result.project is not with_attachment.project
    assert result.attachments[0].basename == "camera-board.png"
    assert result.messages[0].reference_ids == ("image-1",)
    serialized = result.model_dump_json().casefold()
    for forbidden in ("path", "base64", "raw_bytes", "content", "mime", "file_url"):
        assert forbidden not in serialized


def test_attachment_rejects_paths_and_message_requires_known_reference(
    workflow_snapshot,
) -> None:
    port, _ = _runtime(workflow_snapshot)
    session = _session(port)
    with pytest.raises(ValidationError):
        AttachmentProjectionRequest(
            session_id="session-1",
            reference_id="file-1",
            type=AttachmentProjectionType.FILE,
            basename="C:\\workspace\\secret.txt",
            summary="Unsafe path.",
            size_bytes=10,
            timestamp=LATER,
        )
    request = EngineeringChatRequest(
        session_id="session-1",
        message_id="message-1",
        role=EngineeringChatRole.USER,
        summary="Review a missing attachment.",
        reference_ids=("missing-1",),
        timestamp=LATER,
    )
    with pytest.raises(
        EngineeringInterfaceRejected, match="interface request rejected"
    ):
        port.submit_message(session, request)


def test_duplicate_and_cross_session_inputs_fail_closed(workflow_snapshot) -> None:
    port, _ = _runtime(workflow_snapshot)
    session = _session(port)
    request = AttachmentProjectionRequest(
        session_id="session-1",
        reference_id="file-1",
        type=AttachmentProjectionType.FILE,
        basename="design.txt",
        summary="Design reference metadata.",
        size_bytes=10,
        timestamp=LATER,
    )
    updated = port.project_attachment(session, request)
    with pytest.raises(EngineeringInterfaceRejected):
        port.project_attachment(updated, request)
    cross_session = request.model_copy(update={"session_id": "session-2"})
    with pytest.raises(EngineeringInterfaceRejected):
        port.project_attachment(session, cross_session)
