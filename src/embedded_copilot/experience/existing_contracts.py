"""Narrow adapter for existing read-only Copilot contracts."""

from embedded_copilot.copilot.context import DesignSessionContext
from embedded_copilot.copilot.models import (
    ArtifactView,
    DesignStage,
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
    WorkflowProgressStatus,
    safe_identifier,
    safe_optional_summary,
    safe_summary,
    utc_datetime,
)
from embedded_copilot.copilot.progress import WorkflowProgress
from embedded_copilot.copilot.workspace import ProjectWorkspace

__all__ = [
    "ArtifactView",
    "DesignSessionContext",
    "DesignStage",
    "ProjectWorkspace",
    "WorkflowProgress",
    "WorkflowProgressStatus",
    "WorkspaceFileSource",
    "WorkspaceFileStatus",
    "WorkspaceFileType",
    "safe_identifier",
    "safe_optional_summary",
    "safe_summary",
    "utc_datetime",
]
