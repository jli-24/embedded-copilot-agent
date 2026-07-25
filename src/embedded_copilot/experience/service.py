from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import datetime

from embedded_copilot.experience.existing_contracts import ProjectWorkspace
from embedded_copilot.experience.models import (
    ExperienceRequest,
    ExperienceResponse,
    ReviewIntent,
    ReviewReceipt,
)
from embedded_copilot.experience.ports import (
    ArtifactViewReadPort,
    BlueprintReadPort,
    KnowledgeTraceReadPort,
    WorkflowProgressReadPort,
    WorkspaceReadPort,
)
from embedded_copilot.experience.presentation import (
    ArtifactViewerResponse,
    FileExplorerResponse,
    ProgressResponse,
    WorkspacePresentationService,
)
from embedded_copilot.experience.review import ProcessLocalReviewRepository
from embedded_copilot.experience.viewer import ArtifactViewerService


class ExperienceNotFound(LookupError):
    """A requested Experience reference is not bound to the Workspace."""


class ProcessLocalExperienceService:
    def __init__(
        self,
        *,
        workspace_port: WorkspaceReadPort,
        artifact_port: ArtifactViewReadPort,
        blueprint_port: BlueprintReadPort,
        knowledge_trace_port: KnowledgeTraceReadPort,
        progress_port: WorkflowProgressReadPort,
        review_repository: ProcessLocalReviewRepository,
        clock: Callable[[], datetime],
    ) -> None:
        self._workspace_port = workspace_port
        self._review_repository = review_repository
        self._clock = clock
        self._workspace_presenter = WorkspacePresentationService(
            workspace_port=workspace_port,
            knowledge_trace_port=knowledge_trace_port,
            progress_port=progress_port,
        )
        self._artifact_viewer = ArtifactViewerService(
            workspace_port=workspace_port,
            artifact_port=artifact_port,
            blueprint_port=blueprint_port,
        )

    def get_workspace(self, request: ExperienceRequest) -> ExperienceResponse:
        return self._workspace_presenter.get_workspace(request)

    def get_artifacts(self, request: ExperienceRequest) -> ArtifactViewerResponse:
        return self._artifact_viewer.get_artifacts(request)

    def get_files(self, request: ExperienceRequest) -> FileExplorerResponse:
        return self._workspace_presenter.get_files(request)

    def get_progress(self, request: ExperienceRequest) -> ProgressResponse:
        return self._workspace_presenter.get_progress(request)

    def record_review(self, intent: ReviewIntent) -> ReviewReceipt:
        candidate = ReviewIntent.model_validate(
            copy.deepcopy(intent.model_dump(mode="python"))
        )
        workspace = ProjectWorkspace.model_validate(
            copy.deepcopy(
                self._workspace_port.get(candidate.session_id).model_dump(mode="python")
            )
        )
        if workspace.session.session_id.casefold() != candidate.session_id.casefold():
            raise ExperienceNotFound("Workspace session identity is inconsistent")
        if candidate.artifact_id.casefold() not in {
            item.casefold() for item in workspace.session.artifact_ids
        }:
            raise ExperienceNotFound("Artifact reference is not bound to the session")
        if candidate.timestamp < workspace.session.created_at:
            raise ValueError("review intent precedes the session")
        self._review_repository.add(candidate)
        return ReviewReceipt(
            intent_id=candidate.intent_id,
            session_id=candidate.session_id,
            artifact_id=candidate.artifact_id,
            action=candidate.action,
            source=candidate.source,
            recorded_at=self._clock(),
        )
