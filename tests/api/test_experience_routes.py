from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from embedded_copilot.api.main import create_app
from embedded_copilot.conversation.models import ConversationMessage, ConversationTurn
from embedded_copilot.copilot.session import create_session
from embedded_copilot.copilot.workspace import ProjectWorkspace, create_workspace
from embedded_copilot.experience.models import (
    ExperienceResponse,
    ReviewIntent,
    ReviewReceipt,
    ViewerState,
    ViewerStatus,
)
from embedded_copilot.experience.presentation import (
    ArtifactViewerResponse,
    ExperienceProjectionUnavailable,
    FileExplorerResponse,
    ProgressResponse,
)
from embedded_copilot.experience.review import ReviewStateConflict
from embedded_copilot.experience.service import ExperienceNotFound
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings

UTC = timezone.utc
CREATED = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(
            answer="Existing chat remains available.", trace_id=trace_id
        )


class _WorkspaceService:
    def __init__(self) -> None:
        self.workspace = create_workspace(
            create_session(
                session_id="session:1",
                project_name="Security Terminal",
                user_requirement="Review an existing embedded design.",
                created_at=CREATED,
            )
        )

    async def create_session(self, **kwargs: object) -> ProjectWorkspace:
        return self.workspace

    def get_session(self, session_id: str, *, trace_id: str) -> ProjectWorkspace:
        return self.workspace

    async def send_message(
        self,
        message: ConversationMessage,
        *,
        trace_id: str,
    ) -> ConversationTurn:
        raise AssertionError("message endpoint is not used by this fake")


class _ExperienceService:
    def __init__(self, *, outcome: str = "success") -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str]] = []

    def get_workspace(self, request) -> ExperienceResponse:
        self._record("workspace", request.session_id)
        return ExperienceResponse(
            session_id=request.session_id,
            project_summary="Security Terminal Review an existing embedded design.",
            file_count=0,
            message_count=0,
            progress_count=0,
            viewer_state=ViewerState(status=ViewerStatus.READY),
        )

    def get_artifacts(self, request) -> ArtifactViewerResponse:
        self._record("artifact-view", request.session_id)
        return ArtifactViewerResponse(
            session_id=request.session_id,
            viewer_state=ViewerState(status=ViewerStatus.EMPTY),
        )

    def get_files(self, request) -> FileExplorerResponse:
        self._record("files", request.session_id)
        return FileExplorerResponse(
            session_id=request.session_id,
            viewer_state=ViewerState(status=ViewerStatus.EMPTY),
        )

    def get_progress(self, request) -> ProgressResponse:
        self._record("progress", request.session_id)
        return ProgressResponse(
            session_id=request.session_id,
            viewer_state=ViewerState(status=ViewerStatus.EMPTY),
        )

    def record_review(self, intent: ReviewIntent) -> ReviewReceipt:
        self._record("review", intent.session_id)
        return ReviewReceipt(
            intent_id=intent.intent_id,
            session_id=intent.session_id,
            artifact_id=intent.artifact_id,
            action=intent.action,
            recorded_at=CREATED + timedelta(minutes=2),
        )

    def _record(self, operation: str, session_id: str) -> None:
        self.calls.append((operation, session_id))
        error = {
            "not_found": ExperienceNotFound("PRIVATE_NOT_FOUND"),
            "conflict": ReviewStateConflict("PRIVATE_CONFLICT"),
            "unavailable": ExperienceProjectionUnavailable("PRIVATE_PROJECTION"),
            "timeout": TimeoutError("PRIVATE_TIMEOUT"),
        }.get(self.outcome)
        if error is not None:
            raise error


async def _request(
    method: str,
    path: str,
    *,
    experience_service: _ExperienceService | None,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    app = create_app(
        service=_ChatService(),
        workspace_service=_WorkspaceService(),
        experience_service=experience_service,
        settings=Settings(_env_file=None),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)


def test_experience_read_endpoints_and_review_are_additive() -> None:
    service = _ExperienceService()

    responses = [
        asyncio.run(_request("GET", path, experience_service=service))
        for path in (
            "/api/v1/copilot/sessions/session:1/workspace",
            "/api/v1/copilot/sessions/session:1/artifact-view",
            "/api/v1/copilot/sessions/session:1/files",
            "/api/v1/copilot/sessions/session:1/progress",
        )
    ]
    review = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions/session:1/review",
            experience_service=service,
            json={
                "intent_id": "review:1",
                "artifact_id": "artifact:1",
                "action": "APPROVE_INTENT",
                "comment_summary": "Record user intent for review.",
                "timestamp": (CREATED + timedelta(minutes=1)).isoformat(),
            },
        )
    )

    assert [response.status_code for response in responses] == [200, 200, 200, 200]
    assert all(response.json()["session_id"] == "session:1" for response in responses)
    assert review.status_code == 202
    assert review.json()["source"] == "user"
    assert review.json()["status"] == "RECORDED"
    assert review.json()["handoff"] == "engineering_agent_review"
    assert service.calls == [
        ("workspace", "session:1"),
        ("artifact-view", "session:1"),
        ("files", "session:1"),
        ("progress", "session:1"),
        ("review", "session:1"),
    ]


def test_missing_experience_service_returns_safe_503() -> None:
    response = asyncio.run(
        _request(
            "GET",
            "/api/v1/copilot/sessions/session:1/workspace",
            experience_service=None,
        )
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Copilot experience service is unavailable.",
        "trace_id": response.headers["x-trace-id"],
    }


@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_detail"),
    (
        ("not_found", 404, "Copilot experience resource was not found."),
        ("conflict", 409, "Copilot experience state conflict."),
        ("unavailable", 503, "Copilot experience projection is unavailable."),
        ("timeout", 504, "Copilot experience request timed out."),
    ),
)
def test_experience_errors_map_without_private_details(
    outcome: str,
    expected_status: int,
    expected_detail: str,
) -> None:
    response = asyncio.run(
        _request(
            "GET",
            "/api/v1/copilot/sessions/session:1/workspace",
            experience_service=_ExperienceService(outcome=outcome),
        )
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert response.json()["trace_id"] == response.headers["x-trace-id"]
    assert "PRIVATE_" not in response.text


def test_review_validation_maps_to_safe_422() -> None:
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions/session:1/review",
            experience_service=_ExperienceService(),
            json={
                "intent_id": "review:1",
                "artifact_id": "artifact:1",
                "action": "APPROVE_INTENT",
                "source": "model",
                "timestamp": (CREATED + timedelta(minutes=1)).isoformat(),
            },
        )
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed."
    assert response.json()["trace_id"] == response.headers["x-trace-id"]


def test_files_schema_is_metadata_only() -> None:
    schema = FileExplorerResponse.model_json_schema()
    serialized = str(schema).casefold()
    properties = schema["$defs"]["FileMetadataView"]["properties"]

    assert tuple(properties) == (
        "file_id",
        "basename",
        "file_type",
        "size",
        "source",
        "status",
        "timestamp",
    )

    for prohibited in ("download", "open", "preview", "path", "content", "bytes"):
        assert prohibited not in serialized


def test_default_runtime_is_process_local_and_has_no_default_model_provider() -> None:
    async def exercise() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                created = await client.post(
                    "/api/v1/copilot/sessions",
                    json={
                        "session_id": "session:default",
                        "project_name": "Default Workspace",
                        "user_requirement": "Record a controlled change intent.",
                        "created_at": CREATED.isoformat(),
                    },
                )
                workspace = await client.get(
                    "/api/v1/copilot/sessions/session:default/workspace"
                )
                reasoning = await client.post(
                    "/api/v1/copilot/sessions/session:default/messages",
                    json={
                        "message_id": "message:1",
                        "content_summary": "Explain this project.",
                        "created_at": (CREATED + timedelta(minutes=1)).isoformat(),
                    },
                )
                return created, workspace, reasoning

    created, workspace, reasoning = asyncio.run(exercise())

    assert created.status_code == 201
    assert workspace.status_code == 200
    assert workspace.json()["session_id"] == "session:default"
    assert reasoning.status_code == 503
    assert reasoning.json()["detail"] == "Copilot workspace service is unavailable."


def test_new_default_runtime_does_not_recover_previous_sessions() -> None:
    async def create_then_read_from_new_app() -> httpx.Response:
        first = create_app(service=_ChatService(), settings=Settings(_env_file=None))
        async with first.router.lifespan_context(first):
            transport = httpx.ASGITransport(app=first, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/api/v1/copilot/sessions",
                    json={
                        "session_id": "session:ephemeral",
                        "project_name": "Ephemeral Workspace",
                        "user_requirement": "Remain process local.",
                        "created_at": CREATED.isoformat(),
                    },
                )
                assert response.status_code == 201

        second = create_app(service=_ChatService(), settings=Settings(_env_file=None))
        async with second.router.lifespan_context(second):
            transport = httpx.ASGITransport(app=second, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(
                    "/api/v1/copilot/sessions/session:ephemeral/workspace"
                )

    response = asyncio.run(create_then_read_from_new_app())

    assert response.status_code == 404
