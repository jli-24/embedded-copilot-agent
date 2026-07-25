from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.events import KnowledgeTrace
from embedded_copilot.copilot.models import (
    KnowledgeTraceAction,
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
    WorkflowProgressStatus,
)
from embedded_copilot.copilot.progress import WorkflowProgress
from embedded_copilot.copilot.session import (
    bind_artifact,
    create_session,
    project_artifact_view,
)
from embedded_copilot.copilot.workspace import (
    ProjectWorkspace,
    WorkspaceFile,
    create_workspace,
    record_knowledge_trace,
    record_progress,
    track_file,
)
from embedded_copilot.experience.models import (
    BlueprintEdge,
    BlueprintNode,
    BlueprintProjection,
    ExperienceRequest,
    ViewerStatus,
)
from embedded_copilot.experience.presentation import (
    ExperienceProjectionUnavailable,
    FileExplorerResponse,
    WorkspacePresentationService,
)
from embedded_copilot.experience.viewer import ArtifactViewerService
from tests.copilot.test_artifact_view import artifact

UTC = timezone.utc
CREATED = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)


def _workspace(*, include_artifact: bool = True) -> ProjectWorkspace:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review the existing ESP32 design.",
        created_at=CREATED,
    )
    if include_artifact:
        context = bind_artifact(
            context,
            artifact_id="artifact:1",
            artifact=artifact(),
            updated_at=CREATED + timedelta(minutes=1),
        )
    workspace = create_workspace(context)
    workspace = track_file(
        workspace,
        WorkspaceFile(
            file_id="file:1",
            filename="esp32-datasheet.pdf",
            file_type=WorkspaceFileType.DATASHEET,
            size_bytes=2048,
            source=WorkspaceFileSource.INPUT,
            status=WorkspaceFileStatus.REFERENCED,
            created_at=CREATED + timedelta(minutes=2),
        ),
    )
    workspace = record_progress(
        workspace,
        WorkflowProgress(
            stage="REQUIREMENT_ANALYSIS",
            status=WorkflowProgressStatus.PENDING,
            summary="Requirement review is pending.",
            updated_at=CREATED + timedelta(minutes=3),
        ),
    )
    return record_knowledge_trace(
        workspace,
        KnowledgeTrace(
            query="Review existing Datasheet sources.",
            source_ids=("datasheet:1",),
            result_count=1,
            action=KnowledgeTraceAction.VIEWED,
        ),
    )


class _WorkspacePort:
    def __init__(self, workspace: ProjectWorkspace) -> None:
        self.workspace = workspace

    def get(self, session_id: str) -> ProjectWorkspace:
        assert session_id == self.workspace.session.session_id
        return ProjectWorkspace.model_validate(self.workspace.model_dump(mode="python"))


class _ArtifactPort:
    def get(self, session_id: str, artifact_id: str):
        assert session_id == "session:1"
        if artifact_id != "artifact:1":
            return None
        return project_artifact_view(artifact_id=artifact_id, artifact=artifact())


class _BlueprintPort:
    def __init__(self, projection: BlueprintProjection | None) -> None:
        self.projection = projection

    def get(self, session_id: str, artifact_id: str) -> BlueprintProjection | None:
        return self.projection


class _TracePort:
    def __init__(self, workspace: ProjectWorkspace) -> None:
        self.workspace = workspace

    def list(self, session_id: str):
        assert session_id == self.workspace.session.session_id
        return self.workspace.knowledge_traces


class _ProgressPort:
    def __init__(self, workspace: ProjectWorkspace) -> None:
        self.workspace = workspace

    def list(self, session_id: str):
        assert session_id == self.workspace.session.session_id
        return self.workspace.progress


def _blueprint(*, with_edge: bool = True) -> BlueprintProjection:
    nodes = (
        BlueprintNode(node_id="node:esp32", label="ESP32-S3", kind="module"),
        BlueprintNode(node_id="node:pir", label="PIR", kind="module"),
    )
    edges = (
        (
            BlueprintEdge(
                edge_id="edge:existing",
                source_node_id="node:esp32",
                target_node_id="node:pir",
                label="Existing artifact relationship",
            ),
        )
        if with_edge
        else ()
    )
    return BlueprintProjection(
        session_id="session:1",
        artifact_id="artifact:1",
        nodes=nodes,
        edges=edges,
    )


def test_artifact_viewer_preserves_source_and_existing_relationships() -> None:
    source = artifact()
    before = source.model_dump_json()
    service = ArtifactViewerService(
        workspace_port=_WorkspacePort(_workspace()),
        artifact_port=_ArtifactPort(),
        blueprint_port=_BlueprintPort(_blueprint()),
    )

    response = service.get_artifacts(ExperienceRequest(session_id="session:1"))

    assert response.session_id == "session:1"
    assert response.viewer_state.status is ViewerStatus.READY
    assert [item.artifact_id for item in response.artifacts] == ["artifact:1"]
    presented = response.artifacts[0]
    assert [item.edge_id for item in presented.blueprint_summary.edges] == [
        "edge:existing"
    ]
    assert presented.evidence_summary[0].source_id == "datasheet:1"
    assert presented.decision_summary[0].evidence_ids == ("evidence:1",)
    assert source.model_dump_json() == before


def test_blueprint_with_no_relationships_is_unresolved_without_invention() -> None:
    service = ArtifactViewerService(
        workspace_port=_WorkspacePort(_workspace()),
        artifact_port=_ArtifactPort(),
        blueprint_port=_BlueprintPort(_blueprint(with_edge=False)),
    )

    response = service.get_artifacts(ExperienceRequest(session_id="session:1"))
    summary = response.artifacts[0].blueprint_summary

    assert summary.viewer_state.status is ViewerStatus.EMPTY
    assert summary.edges == ()
    assert summary.viewer_state.detail == "Blueprint relationships are unresolved."


def test_empty_blueprint_is_unavailable_without_invention() -> None:
    projection = BlueprintProjection(
        session_id="session:1",
        artifact_id="artifact:1",
    )
    service = ArtifactViewerService(
        workspace_port=_WorkspacePort(_workspace()),
        artifact_port=_ArtifactPort(),
        blueprint_port=_BlueprintPort(projection),
    )

    response = service.get_artifacts(ExperienceRequest(session_id="session:1"))
    summary = response.artifacts[0].blueprint_summary

    assert summary.viewer_state.status is ViewerStatus.UNAVAILABLE
    assert summary.viewer_state.detail == "No verified relationship available"
    assert summary.nodes == ()
    assert summary.edges == ()


def test_artifact_viewer_returns_empty_for_workspace_without_artifacts() -> None:
    service = ArtifactViewerService(
        workspace_port=_WorkspacePort(_workspace(include_artifact=False)),
        artifact_port=_ArtifactPort(),
        blueprint_port=_BlueprintPort(None),
    )

    response = service.get_artifacts(ExperienceRequest(session_id="session:1"))

    assert response.artifacts == ()
    assert response.viewer_state.status is ViewerStatus.EMPTY


def test_missing_bound_artifact_projection_fails_without_hiding_state() -> None:
    class MissingArtifactPort:
        def get(self, session_id: str, artifact_id: str):
            return None

    service = ArtifactViewerService(
        workspace_port=_WorkspacePort(_workspace()),
        artifact_port=MissingArtifactPort(),
        blueprint_port=_BlueprintPort(None),
    )

    with pytest.raises(ExperienceProjectionUnavailable, match="Artifact projection"):
        service.get_artifacts(ExperienceRequest(session_id="session:1"))


def test_workspace_files_progress_and_trace_are_safe_presentations() -> None:
    workspace = _workspace()
    workspace_port = _WorkspacePort(workspace)
    service = WorkspacePresentationService(
        workspace_port=workspace_port,
        knowledge_trace_port=_TracePort(workspace),
        progress_port=_ProgressPort(workspace),
    )

    overview = service.get_workspace(ExperienceRequest(session_id="session:1"))
    files = service.get_files(ExperienceRequest(session_id="session:1"))
    progress = service.get_progress(ExperienceRequest(session_id="session:1"))

    assert overview.session_id == files.session_id == progress.session_id == "session:1"
    assert overview.knowledge_traces == workspace.knowledge_traces
    assert files.files[0].basename == "esp32-datasheet.pdf"
    assert files.files[0].timestamp == CREATED + timedelta(minutes=2)
    assert not hasattr(files.files[0], "filename")
    assert not hasattr(files.files[0], "created_at")
    assert not hasattr(files.files[0], "path")
    assert progress.items[0].percent == 0
    assert progress.items[0].is_error is False


def test_file_explorer_response_rejects_file_actions_and_content() -> None:
    response = FileExplorerResponse(
        session_id="session:1",
        viewer_state={"status": "EMPTY"},
        files=(),
    )
    payload = response.model_dump(mode="python")

    for forbidden in (
        "download",
        "open",
        "preview",
        "path",
        "content",
        "bytes",
    ):
        with pytest.raises(ValidationError):
            FileExplorerResponse.model_validate({**payload, forbidden: "unsafe"})
