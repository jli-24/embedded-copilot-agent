from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from embedded_copilot.api.main import create_app
from embedded_copilot.conversation.models import (
    ConversationIntent,
    ConversationMessage,
    ConversationTurn,
)
from embedded_copilot.conversation.repository import (
    ConversationNotFound,
    ConversationStateConflict,
)
from embedded_copilot.copilot.session import create_session
from embedded_copilot.copilot.workspace import ProjectWorkspace, create_workspace
from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
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
    def __init__(self, *, outcome: str = "success") -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str]] = []
        self.workspace = create_workspace(
            create_session(
                session_id="session:1",
                project_name="Security Terminal",
                user_requirement="Review an existing embedded design.",
                created_at=CREATED,
            )
        )

    async def create_session(
        self,
        *,
        session_id: str,
        project_name: str,
        user_requirement: str,
        created_at: datetime,
        trace_id: str,
    ) -> ProjectWorkspace:
        self.calls.append(("create", trace_id))
        self._raise_if_requested()
        return self.workspace

    def get_session(self, session_id: str, *, trace_id: str) -> ProjectWorkspace:
        self.calls.append(("get", trace_id))
        self._raise_if_requested()
        return self.workspace

    async def send_message(
        self,
        message: ConversationMessage,
        *,
        trace_id: str,
    ) -> ConversationTurn:
        self.calls.append(("message", trace_id))
        self._raise_if_requested()
        return ConversationTurn(
            session_id=message.session_id,
            intent=ConversationIntent.GENERAL,
            answer_summary="Request-scoped reasoning suggestion.",
            handoff="general_response",
        )

    def _raise_if_requested(self) -> None:
        error = {
            "not_found": ConversationNotFound("PRIVATE_NOT_FOUND"),
            "conflict": ConversationStateConflict("PRIVATE_CONFLICT"),
            "unavailable": ModelProviderUnavailable("PRIVATE_PROVIDER"),
            "timeout": TimeoutError("PRIVATE_TIMEOUT"),
        }.get(self.outcome)
        if error is not None:
            raise error


async def _request(
    method: str,
    path: str,
    *,
    workspace_service: _WorkspaceService | None,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    app = create_app(
        service=_ChatService(),
        workspace_service=workspace_service,
        settings=Settings(_env_file=None),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)


def test_create_get_and_message_endpoints_are_additive() -> None:
    service = _WorkspaceService()
    create_response = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions",
            workspace_service=service,
            json={
                "session_id": "session:1",
                "project_name": "Security Terminal",
                "user_requirement": "Review an existing embedded design.",
                "created_at": CREATED.isoformat(),
            },
        )
    )
    get_response = asyncio.run(
        _request(
            "GET",
            "/api/v1/copilot/sessions/session:1",
            workspace_service=service,
        )
    )
    message_response = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions/session:1/messages",
            workspace_service=service,
            json={
                "message_id": "message:1",
                "content_summary": "Explain the available evidence.",
                "created_at": (CREATED + timedelta(minutes=1)).isoformat(),
            },
        )
    )

    assert create_response.status_code == 201
    assert get_response.status_code == 200
    assert message_response.status_code == 200
    assert create_response.json()["session"]["session_id"] == "session:1"
    assert get_response.json()["session"]["session_id"] == "session:1"
    assert message_response.json()["answer_summary"] == (
        "Request-scoped reasoning suggestion."
    )
    trace_ids = [trace_id for _, trace_id in service.calls]
    assert all(trace_ids)
    assert create_response.headers["x-trace-id"] == trace_ids[0]
    assert get_response.headers["x-trace-id"] == trace_ids[1]
    assert message_response.headers["x-trace-id"] == trace_ids[2]


def test_missing_workspace_service_returns_safe_503_without_mock_default() -> None:
    response = asyncio.run(
        _request(
            "GET",
            "/api/v1/copilot/sessions/session:1",
            workspace_service=None,
        )
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Copilot workspace service is unavailable.",
        "trace_id": response.headers["x-trace-id"],
    }


@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_detail"),
    (
        ("not_found", 404, "Copilot session was not found."),
        ("conflict", 409, "Copilot session state conflict."),
        ("unavailable", 503, "Copilot workspace service is unavailable."),
        ("timeout", 504, "Copilot workspace request timed out."),
    ),
)
def test_workspace_errors_map_without_private_details(
    outcome: str,
    expected_status: int,
    expected_detail: str,
) -> None:
    response = asyncio.run(
        _request(
            "GET",
            "/api/v1/copilot/sessions/session:1",
            workspace_service=_WorkspaceService(outcome=outcome),
        )
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert response.json()["trace_id"] == response.headers["x-trace-id"]
    assert "PRIVATE_" not in response.text


def test_workspace_validation_maps_to_safe_422() -> None:
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions",
            workspace_service=_WorkspaceService(),
            json={
                "session_id": "session:1",
                "project_name": "   ",
                "user_requirement": "Review an existing embedded design.",
                "created_at": CREATED.isoformat(),
            },
        )
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed."
    assert response.json()["trace_id"] == response.headers["x-trace-id"]
