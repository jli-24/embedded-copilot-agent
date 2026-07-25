"""Read-only Copilot Workspace contracts."""

from embedded_copilot.copilot.context import ChatMessage, DesignSessionContext
from embedded_copilot.copilot.events import ApprovalEvent, KnowledgeTrace
from embedded_copilot.copilot.models import (
    ApprovalAction,
    ArtifactDecisionView,
    ArtifactEvidenceView,
    ArtifactView,
    ChatRole,
    DesignStage,
    KnowledgeTraceAction,
    ModelInputType,
    ModelRequest,
    ModelTaskType,
    SessionApprovalStatus,
    WorkflowProgressStatus,
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
)
from embedded_copilot.copilot.progress import WorkflowProgress, update_progress
from embedded_copilot.copilot.session import (
    advance_stage,
    bind_artifact,
    create_session,
    project_artifact_view,
)
from embedded_copilot.copilot.workspace import (
    ProjectWorkspace,
    WorkspaceFile,
    create_workspace,
    record_approval_event,
    record_knowledge_trace,
    record_message,
    record_progress,
    track_file,
)

__all__ = [
    "ApprovalAction",
    "ApprovalEvent",
    "ArtifactDecisionView",
    "ArtifactEvidenceView",
    "ArtifactView",
    "ChatMessage",
    "ChatRole",
    "DesignSessionContext",
    "DesignStage",
    "KnowledgeTrace",
    "KnowledgeTraceAction",
    "ModelInputType",
    "ModelRequest",
    "ModelTaskType",
    "SessionApprovalStatus",
    "WorkflowProgress",
    "WorkflowProgressStatus",
    "WorkspaceFile",
    "WorkspaceFileSource",
    "WorkspaceFileStatus",
    "WorkspaceFileType",
    "ProjectWorkspace",
    "advance_stage",
    "bind_artifact",
    "create_session",
    "create_workspace",
    "project_artifact_view",
    "record_approval_event",
    "record_knowledge_trace",
    "record_message",
    "record_progress",
    "track_file",
    "update_progress",
]
