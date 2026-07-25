from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from embedded_copilot.conversation.context import ContextResolver
from embedded_copilot.conversation.models import ConversationMessage, ConversationTurn
from embedded_copilot.conversation.repository import (
    ConversationNotFound,
    ProcessLocalConversationRepository,
)
from embedded_copilot.conversation.router import IntentRouter
from embedded_copilot.conversation.service import ConversationService
from embedded_copilot.experience.existing_contracts import (
    ArtifactView,
    DesignSessionContext,
    ProjectWorkspace,
    WorkflowProgress,
)
from embedded_copilot.experience.models import BlueprintProjection
from embedded_copilot.experience.review import ProcessLocalReviewRepository
from embedded_copilot.experience.service import (
    ExperienceNotFound,
    ProcessLocalExperienceService,
)
from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.models import ModelInput
from embedded_copilot.schemas.knowledge_trace import KnowledgeTrace
from embedded_copilot.schemas.model import ModelRequest


class _UnavailableReasoningPort:
    async def reason(self, request: ModelRequest, model_input: ModelInput):
        raise ModelProviderUnavailable("No reasoning provider is configured")


class _ArtifactProjectionPort:
    def get(self, session_id: str, artifact_id: str) -> ArtifactView | None:
        return None


class _WorkspaceProjectionPort:
    def __init__(self, repository: ProcessLocalConversationRepository) -> None:
        self._repository = repository

    def get(self, session_id: str) -> ProjectWorkspace:
        try:
            return self._repository.get(session_id)
        except ConversationNotFound as error:
            raise ExperienceNotFound("Workspace projection was not found") from error


class _BlueprintProjectionPort:
    def get(self, session_id: str, artifact_id: str) -> BlueprintProjection | None:
        return None


class _KnowledgeTraceProjectionPort:
    def __init__(self, repository: ProcessLocalConversationRepository) -> None:
        self._repository = repository

    def list(self, session_id: str) -> tuple[KnowledgeTrace, ...]:
        try:
            return self._repository.get(session_id).knowledge_traces
        except ConversationNotFound as error:
            raise ExperienceNotFound(
                "Knowledge trace projection was not found"
            ) from error


class _WorkflowProgressProjectionPort:
    def __init__(self, repository: ProcessLocalConversationRepository) -> None:
        self._repository = repository

    def list(self, session_id: str) -> tuple[WorkflowProgress, ...]:
        try:
            return self._repository.get(session_id).progress
        except ConversationNotFound as error:
            raise ExperienceNotFound("Progress projection was not found") from error


class ProcessLocalWorkspaceService:
    def __init__(
        self,
        *,
        repository: ProcessLocalConversationRepository,
        conversation_service: ConversationService,
    ) -> None:
        self._repository = repository
        self._conversation_service = conversation_service

    async def create_session(
        self,
        *,
        session_id: str,
        project_name: str,
        user_requirement: str,
        created_at: datetime,
        trace_id: str,
    ) -> ProjectWorkspace:
        context = DesignSessionContext(
            session_id=session_id,
            project_name=project_name,
            user_requirement=user_requirement,
            created_at=created_at,
            updated_at=created_at,
        )
        workspace = ProjectWorkspace(session=context)
        self._repository.add(workspace)
        return self._repository.get(session_id)

    def get_session(self, session_id: str, *, trace_id: str) -> ProjectWorkspace:
        return self._repository.get(session_id)

    async def send_message(
        self,
        message: ConversationMessage,
        *,
        trace_id: str,
    ) -> ConversationTurn:
        return await self._conversation_service.send_message(message)


@dataclass(frozen=True)
class ExperienceRuntime:
    workspace_service: ProcessLocalWorkspaceService
    experience_service: ProcessLocalExperienceService


def build_experience_runtime() -> ExperienceRuntime:
    repository = ProcessLocalConversationRepository()
    conversation_service = ConversationService(
        repository=repository,
        context_resolver=ContextResolver(),
        intent_router=IntentRouter(),
        reasoning=_UnavailableReasoningPort(),
    )
    workspace_service = ProcessLocalWorkspaceService(
        repository=repository,
        conversation_service=conversation_service,
    )
    experience_service = ProcessLocalExperienceService(
        workspace_port=_WorkspaceProjectionPort(repository),
        artifact_port=_ArtifactProjectionPort(),
        blueprint_port=_BlueprintProjectionPort(),
        knowledge_trace_port=_KnowledgeTraceProjectionPort(repository),
        progress_port=_WorkflowProgressProjectionPort(repository),
        review_repository=ProcessLocalReviewRepository(),
        clock=lambda: datetime.now(timezone.utc),
    )
    return ExperienceRuntime(
        workspace_service=workspace_service,
        experience_service=experience_service,
    )
