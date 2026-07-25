from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.context import ChatMessage
from embedded_copilot.copilot.events import ApprovalEvent, KnowledgeTrace
from embedded_copilot.copilot.models import (
    ApprovalAction,
    ChatRole,
    KnowledgeTraceAction,
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
)
from embedded_copilot.copilot.session import bind_artifact, create_session
from embedded_copilot.copilot.workspace import (
    ProjectWorkspace,
    WorkspaceFile,
    create_workspace,
    record_approval_event,
    record_knowledge_trace,
    record_message,
    track_file,
)

from tests.copilot.test_artifact_view import artifact

UTC = timezone.utc
CREATED = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)


def _workspace() -> ProjectWorkspace:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review an existing embedded design.",
        created_at=CREATED,
    )
    context = bind_artifact(
        context,
        artifact_id="artifact:1",
        artifact=artifact(),
        updated_at=CREATED + timedelta(minutes=1),
    )
    return create_workspace(context)


def test_workspace_tracks_file_metadata_without_file_content() -> None:
    workspace = _workspace()
    file = WorkspaceFile(
        file_id="file:1",
        filename="hardware_design.json",
        file_type=WorkspaceFileType.ARTIFACT,
        size_bytes=0,
        source=WorkspaceFileSource.GENERATED,
        status=WorkspaceFileStatus.GENERATED,
        created_at=CREATED + timedelta(minutes=2),
    )

    updated = track_file(workspace, file)

    assert updated.files == (file,)
    assert updated.session.file_ids == ("file:1",)
    assert updated.session.updated_at == file.created_at
    assert workspace.files == ()
    assert set(WorkspaceFile.model_fields) == {
        "file_id",
        "filename",
        "file_type",
        "size_bytes",
        "source",
        "status",
        "created_at",
    }


def test_workspace_file_rejects_paths_content_and_binary_data() -> None:
    base: dict[str, object] = {
        "file_id": "file:1",
        "filename": "main.c",
        "file_type": WorkspaceFileType.SOURCE_CODE,
        "size_bytes": 120,
        "source": WorkspaceFileSource.INPUT,
        "status": WorkspaceFileStatus.UPLOADED,
        "created_at": CREATED,
    }
    for update in (
        {"filename": r"C:\Users\private\main.c"},
        {"filename": "../main.c"},
        {"content": "SOURCE_CODE_SENTINEL"},
        {"pdf_content": "PDF_CONTENT_SENTINEL"},
        {"data": b"BINARY_SENTINEL"},
        {"path": "private/main.c"},
    ):
        with pytest.raises(ValidationError):
            WorkspaceFile.model_validate({**base, **update})


def test_workspace_rejects_duplicate_file_ids() -> None:
    file = WorkspaceFile(
        file_id="file:1",
        filename="main.c",
        file_type=WorkspaceFileType.SOURCE_CODE,
        size_bytes=120,
        source=WorkspaceFileSource.INPUT,
        status=WorkspaceFileStatus.UPLOADED,
        created_at=CREATED + timedelta(minutes=2),
    )
    workspace = track_file(_workspace(), file)

    with pytest.raises(ValueError):
        track_file(
            workspace,
            file.model_copy(update={"file_id": "FILE:1"}),
        )


def test_chat_and_approval_events_cannot_create_domain_facts() -> None:
    workspace = _workspace()
    message = ChatMessage(
        message_id="message:1",
        role=ChatRole.USER,
        content_summary="Request review for adding an MQ-2 component.",
        created_at=CREATED + timedelta(minutes=2),
        references=("artifact:1", "decision:1"),
    )
    approval = ApprovalEvent(
        approval_id="approval:1",
        action=ApprovalAction.APPROVE,
        comment="Engineer approval intent recorded for review.",
        timestamp=CREATED + timedelta(minutes=3),
    )

    with_message = record_message(workspace, message)
    updated = record_approval_event(with_message, approval)

    assert updated.session.artifact_ids == workspace.session.artifact_ids
    assert updated.session.decision_ids == workspace.session.decision_ids
    assert updated.session.approval_status == workspace.session.approval_status
    assert "MQ-2" not in updated.session.model_dump_json()
    assert "components" not in ProjectWorkspace.model_fields


def test_chat_references_must_be_known_to_session() -> None:
    message = ChatMessage(
        message_id="message:1",
        role=ChatRole.USER,
        content_summary="Request review of an existing design.",
        created_at=CREATED + timedelta(minutes=2),
        references=("artifact:missing",),
    )

    with pytest.raises(ValueError):
        record_message(_workspace(), message)


def test_workspace_records_knowledge_trace_without_retrieval_execution() -> None:
    trace = KnowledgeTrace(
        query="Find existing ESP32-S3 Datasheet evidence.",
        source_ids=("datasheet:1",),
        result_count=2,
        action=KnowledgeTraceAction.VIEWED,
    )

    updated = record_knowledge_trace(_workspace(), trace)

    assert updated.knowledge_traces == (trace,)
    assert not hasattr(updated, "retriever")


def test_workspace_serialization_contains_only_ids_and_safe_summaries() -> None:
    workspace = _workspace()
    file = WorkspaceFile(
        file_id="file:1",
        filename="hardware_design.json",
        file_type=WorkspaceFileType.ARTIFACT,
        size_bytes=0,
        source=WorkspaceFileSource.GENERATED,
        status=WorkspaceFileStatus.GENERATED,
        created_at=CREATED + timedelta(minutes=2),
    )
    workspace = track_file(workspace, file)
    workspace = record_message(
        workspace,
        ChatMessage(
            message_id="message:1",
            role=ChatRole.USER,
            content_summary="Review the referenced engineering decision.",
            created_at=CREATED + timedelta(minutes=3),
            references=("artifact:1", "decision:1", "file:1"),
        ),
    )
    serialized = workspace.model_dump_json()

    assert set(ProjectWorkspace.model_fields) == {
        "session",
        "files",
        "messages",
        "progress",
        "approval_events",
        "knowledge_traces",
    }
    for forbidden in (
        "HardwareDesignArtifact",
        "PDF_CONTENT_SENTINEL",
        "SOURCE_CODE_SENTINEL",
        "BINARY_SENTINEL",
        "api_key",
        "credential",
        "provider",
        "model_name",
        "power_tree",
        "gpio_assignments",
    ):
        assert forbidden not in serialized

    with pytest.raises(ValidationError):
        ProjectWorkspace.model_validate(
            {
                **workspace.model_dump(mode="python"),
                "artifact": artifact().model_dump(mode="python"),
            }
        )


def test_workspace_direct_construction_enforces_reference_bindings() -> None:
    workspace = _workspace()
    unbound_message = ChatMessage(
        message_id="message:1",
        role=ChatRole.USER,
        content_summary="Review an existing engineering Artifact.",
        created_at=CREATED + timedelta(minutes=2),
        references=("artifact:missing",),
    )

    with pytest.raises(ValidationError):
        ProjectWorkspace.model_validate(
            {
                **workspace.model_dump(mode="python"),
                "messages": (unbound_message,),
            }
        )

    duplicate = unbound_message.model_copy(update={"references": ()})
    with pytest.raises(ValidationError):
        ProjectWorkspace.model_validate(
            {
                **workspace.model_dump(mode="python"),
                "messages": (duplicate, duplicate),
            }
        )


def test_workspace_direct_construction_enforces_file_indexes() -> None:
    workspace = _workspace()
    file = WorkspaceFile(
        file_id="file:1",
        filename="main.c",
        file_type=WorkspaceFileType.SOURCE_CODE,
        size_bytes=120,
        source=WorkspaceFileSource.INPUT,
        status=WorkspaceFileStatus.UPLOADED,
        created_at=CREATED + timedelta(minutes=2),
    )

    with pytest.raises(ValidationError):
        ProjectWorkspace.model_validate(
            {
                **workspace.model_dump(mode="python"),
                "files": (file,),
            }
        )
