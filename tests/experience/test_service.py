from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from embedded_copilot.copilot.session import (
    bind_artifact,
    create_session,
    project_artifact_view,
)
from embedded_copilot.copilot.workspace import ProjectWorkspace, create_workspace
from embedded_copilot.experience.models import (
    ExperienceRequest,
    ReviewIntent,
    ReviewIntentAction,
    ReviewRecordStatus,
)
from embedded_copilot.experience.review import (
    ProcessLocalReviewRepository,
    ReviewStateConflict,
)
from embedded_copilot.experience.service import (
    ExperienceNotFound,
    ProcessLocalExperienceService,
)
from tests.copilot.test_artifact_view import artifact

UTC = timezone.utc
CREATED = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
RECORDED = CREATED + timedelta(minutes=5)


def _workspace() -> ProjectWorkspace:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review the existing ESP32 design.",
        created_at=CREATED,
    )
    context = bind_artifact(
        context,
        artifact_id="artifact:1",
        artifact=artifact(),
        updated_at=CREATED + timedelta(minutes=1),
    )
    return create_workspace(context)


class _WorkspacePort:
    def __init__(self, workspace: ProjectWorkspace) -> None:
        self.workspace = workspace

    def get(self, session_id: str) -> ProjectWorkspace:
        assert session_id == self.workspace.session.session_id
        return ProjectWorkspace.model_validate(self.workspace.model_dump(mode="python"))


class _ArtifactPort:
    def get(self, session_id: str, artifact_id: str):
        if artifact_id != "artifact:1":
            return None
        return project_artifact_view(artifact_id=artifact_id, artifact=artifact())


class _BlueprintPort:
    def get(self, session_id: str, artifact_id: str):
        return None


class _TracePort:
    def list(self, session_id: str):
        return ()


class _ProgressPort:
    def list(self, session_id: str):
        return ()


def _service(
    repository: ProcessLocalReviewRepository | None = None,
) -> ProcessLocalExperienceService:
    return ProcessLocalExperienceService(
        workspace_port=_WorkspacePort(_workspace()),
        artifact_port=_ArtifactPort(),
        blueprint_port=_BlueprintPort(),
        knowledge_trace_port=_TracePort(),
        progress_port=_ProgressPort(),
        review_repository=repository or ProcessLocalReviewRepository(),
        clock=lambda: RECORDED,
    )


def _intent(intent_id: str = "review:1") -> ReviewIntent:
    return ReviewIntent(
        intent_id=intent_id,
        session_id="session:1",
        artifact_id="artifact:1",
        action=ReviewIntentAction.APPROVE_INTENT,
        comment_summary="Record user intent for Engineering Agent review.",
        timestamp=CREATED + timedelta(minutes=2),
    )


def test_review_intent_is_recorded_without_lifecycle_mutation() -> None:
    source = _workspace()
    before = source.model_dump_json()
    repository = ProcessLocalReviewRepository()
    service = ProcessLocalExperienceService(
        workspace_port=_WorkspacePort(source),
        artifact_port=_ArtifactPort(),
        blueprint_port=_BlueprintPort(),
        knowledge_trace_port=_TracePort(),
        progress_port=_ProgressPort(),
        review_repository=repository,
        clock=lambda: RECORDED,
    )

    receipt = service.record_review(_intent())

    assert receipt.status is ReviewRecordStatus.RECORDED
    assert receipt.source == "user"
    assert receipt.handoff == "engineering_agent_review"
    assert repository.list("session:1") == (_intent(),)
    assert source.model_dump_json() == before
    assert source.session.approval_status.value == "PROPOSED"
    assert "ApprovalEvent" not in repository.list("session:1")[0].model_dump_json()


def test_review_intent_requires_artifact_binding() -> None:
    intent = _intent().model_copy(update={"artifact_id": "artifact:missing"})

    with pytest.raises(ExperienceNotFound, match="Artifact reference"):
        _service().record_review(intent)


def test_review_repository_rejects_duplicates_and_capacity() -> None:
    repository = ProcessLocalReviewRepository(max_intents_per_session=1)
    service = _service(repository)
    service.record_review(_intent())

    with pytest.raises(ReviewStateConflict, match="already exists"):
        service.record_review(_intent("REVIEW:1"))
    with pytest.raises(ReviewStateConflict, match="capacity"):
        service.record_review(_intent("review:2"))


def test_experience_service_delegates_all_reads_through_ports() -> None:
    service = _service()
    request = ExperienceRequest(session_id="session:1")

    assert service.get_workspace(request).session_id == "session:1"
    assert service.get_artifacts(request).session_id == "session:1"
    assert service.get_files(request).session_id == "session:1"
    assert service.get_progress(request).session_id == "session:1"
