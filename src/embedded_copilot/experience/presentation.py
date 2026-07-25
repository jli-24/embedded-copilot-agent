from __future__ import annotations

import copy
from datetime import datetime

from pydantic import Field, field_validator

from embedded_copilot.experience.existing_contracts import (
    DesignStage,
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
    WorkflowProgressStatus,
    safe_identifier,
    safe_summary,
    utc_datetime,
    ProjectWorkspace,
)
from embedded_copilot.experience.models import (
    BlueprintEdge,
    BlueprintNode,
    ExperienceContractModel,
    ExperienceRequest,
    ExperienceResponse,
    ViewerState,
    ViewerStatus,
)
from embedded_copilot.experience.ports import (
    KnowledgeTraceReadPort,
    WorkflowProgressReadPort,
    WorkspaceReadPort,
)
from embedded_copilot.schemas.knowledge_trace import KnowledgeTrace


class ExperienceProjectionUnavailable(RuntimeError):
    """A required read-only Experience projection is unavailable."""


class ArtifactEvidenceSummary(ExperienceContractModel):
    evidence_id: str
    source_id: str
    summary: str

    @field_validator("evidence_id", "source_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_summary(value, field="summary")


class ArtifactDecisionSummary(ExperienceContractModel):
    decision_id: str
    summary: str
    reason: str
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    status: str
    evidence_ids: tuple[str, ...]

    @field_validator("decision_id", mode="before")
    @classmethod
    def validate_decision_id(cls, value: object) -> str:
        return safe_identifier(value, field="decision_id")

    @field_validator("summary", "reason", "status", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_summary(value, field=info.field_name)


class BlueprintSummary(ExperienceContractModel):
    viewer_state: ViewerState
    nodes: tuple[BlueprintNode, ...] = ()
    edges: tuple[BlueprintEdge, ...] = ()


class ArtifactPresentation(ExperienceContractModel):
    session_id: str
    artifact_id: str
    project_summary: str
    target_platform: str
    blueprint_summary: BlueprintSummary
    evidence_summary: tuple[ArtifactEvidenceSummary, ...] = ()
    decision_summary: tuple[ArtifactDecisionSummary, ...] = ()
    limitations: tuple[str, ...] = ()
    approval_status: str

    @field_validator("session_id", "artifact_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator(
        "project_summary", "target_platform", "approval_status", mode="before"
    )
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_summary(value, field=info.field_name)


class ArtifactViewerResponse(ExperienceContractModel):
    session_id: str
    viewer_state: ViewerState
    artifacts: tuple[ArtifactPresentation, ...] = ()

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        return safe_identifier(value, field="session_id")


class FileMetadataView(ExperienceContractModel):
    file_id: str
    basename: str
    file_type: WorkspaceFileType
    size: int = Field(ge=0)
    source: WorkspaceFileSource
    status: WorkspaceFileStatus
    timestamp: datetime

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, value: object) -> str:
        return safe_identifier(value, field="file_id")

    @field_validator("basename", mode="before")
    @classmethod
    def validate_basename(cls, value: object) -> str:
        return safe_summary(value, field="basename", max_length=255)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime:
        return utc_datetime(value, field="timestamp")


class FileExplorerResponse(ExperienceContractModel):
    session_id: str
    viewer_state: ViewerState
    files: tuple[FileMetadataView, ...] = ()

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        return safe_identifier(value, field="session_id")


class ProgressItem(ExperienceContractModel):
    stage: DesignStage
    status: WorkflowProgressStatus
    summary: str
    percent: int = Field(ge=0, le=100)
    is_error: bool
    updated_at: datetime

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_summary(value, field="summary")

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="updated_at")


class ProgressResponse(ExperienceContractModel):
    session_id: str
    viewer_state: ViewerState
    items: tuple[ProgressItem, ...] = ()

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        return safe_identifier(value, field="session_id")


_PROGRESS_PERCENT = {
    WorkflowProgressStatus.PENDING: 0,
    WorkflowProgressStatus.RUNNING: 50,
    WorkflowProgressStatus.COMPLETED: 100,
    WorkflowProgressStatus.FAILED: 100,
}


class WorkspacePresentationService:
    def __init__(
        self,
        *,
        workspace_port: WorkspaceReadPort,
        knowledge_trace_port: KnowledgeTraceReadPort,
        progress_port: WorkflowProgressReadPort,
    ) -> None:
        self._workspace_port = workspace_port
        self._knowledge_trace_port = knowledge_trace_port
        self._progress_port = progress_port

    def get_workspace(self, request: ExperienceRequest) -> ExperienceResponse:
        workspace = self._workspace(request.session_id)
        traces = tuple(
            KnowledgeTrace.model_validate(copy.deepcopy(item.model_dump(mode="python")))
            for item in self._knowledge_trace_port.list(request.session_id)
        )
        progress = self._progress_port.list(request.session_id)
        summary = " ".join(
            (
                workspace.session.project_name,
                workspace.session.user_requirement,
            )
        )[:512]
        return ExperienceResponse(
            session_id=request.session_id,
            project_summary=summary,
            artifact_ids=workspace.session.artifact_ids,
            file_count=len(workspace.files),
            message_count=len(workspace.messages),
            progress_count=len(progress),
            knowledge_traces=traces,
            viewer_state=ViewerState(status=ViewerStatus.READY),
        )

    def get_files(self, request: ExperienceRequest) -> FileExplorerResponse:
        workspace = self._workspace(request.session_id)
        files = tuple(
            FileMetadataView(
                file_id=item.file_id,
                basename=item.filename,
                file_type=item.file_type,
                size=item.size_bytes,
                source=item.source,
                status=item.status,
                timestamp=item.created_at,
            )
            for item in workspace.files
        )
        return FileExplorerResponse(
            session_id=request.session_id,
            viewer_state=ViewerState(
                status=ViewerStatus.READY if files else ViewerStatus.EMPTY,
            ),
            files=files,
        )

    def get_progress(self, request: ExperienceRequest) -> ProgressResponse:
        self._workspace(request.session_id)
        snapshots = self._progress_port.list(request.session_id)
        items = tuple(
            ProgressItem(
                stage=item.stage,
                status=item.status,
                summary=item.summary,
                percent=_PROGRESS_PERCENT[item.status],
                is_error=item.status is WorkflowProgressStatus.FAILED,
                updated_at=item.updated_at,
            )
            for item in snapshots
        )
        return ProgressResponse(
            session_id=request.session_id,
            viewer_state=ViewerState(
                status=ViewerStatus.READY if items else ViewerStatus.EMPTY,
            ),
            items=items,
        )

    def _workspace(self, session_id: str) -> ProjectWorkspace:
        workspace = ProjectWorkspace.model_validate(
            copy.deepcopy(
                self._workspace_port.get(session_id).model_dump(mode="python")
            )
        )
        if workspace.session.session_id.casefold() != session_id.casefold():
            raise ExperienceProjectionUnavailable(
                "Workspace projection session identity is inconsistent."
            )
        return workspace
