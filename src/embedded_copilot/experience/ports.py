from __future__ import annotations

from typing import Protocol

from embedded_copilot.experience.models import BlueprintProjection
from embedded_copilot.experience.existing_contracts import (
    ArtifactView,
    ProjectWorkspace,
    WorkflowProgress,
)
from embedded_copilot.schemas.knowledge_trace import KnowledgeTrace


class WorkspaceReadPort(Protocol):
    def get(self, session_id: str) -> ProjectWorkspace: ...


class ArtifactViewReadPort(Protocol):
    def get(self, session_id: str, artifact_id: str) -> ArtifactView | None: ...


class BlueprintReadPort(Protocol):
    def get(
        self,
        session_id: str,
        artifact_id: str,
    ) -> BlueprintProjection | None: ...


class KnowledgeTraceReadPort(Protocol):
    def list(self, session_id: str) -> tuple[KnowledgeTrace, ...]: ...


class WorkflowProgressReadPort(Protocol):
    def list(self, session_id: str) -> tuple[WorkflowProgress, ...]: ...
