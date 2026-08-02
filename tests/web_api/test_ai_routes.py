from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from embedded_copilot.ai_runtime import (
    EngineeringChatRequest,
    EngineeringResponse,
    engineering_response_fingerprint,
)
from embedded_copilot.conversation_feedback import (
    create_conversation_feedback_service,
)
from embedded_copilot.engineering_events import (
    EngineeringEvent,
    EngineeringEventType,
    engineering_event_fingerprint,
)
from embedded_copilot.product import create_product_runtime
from embedded_copilot.web_api import create_web_api_app
from tests.web_api.conftest import AttachmentFake, PreparationFake, RepositoryFake

_TIME = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)


@dataclass
class EngineeringChatFake:
    calls: list[EngineeringChatRequest] = field(default_factory=list)

    async def chat(self, request: EngineeringChatRequest) -> EngineeringResponse:
        self.calls.append(request.model_copy(deep=True))
        event_values = dict(
            sequence=1,
            event_type=EngineeringEventType.COMPLETED,
            stage="ENGINEERING_CHAT",
            status="COMPLETED",
            count=1,
            reference_id=request.request_id,
            timestamp=request.requested_at,
        )
        event = EngineeringEvent(
            **event_values,
            fingerprint=engineering_event_fingerprint(**event_values),
        )
        values = dict(
            request_id=request.request_id,
            project_id=request.project_id,
            requirement_analysis="The requirement needs an explicit power budget.",
            architecture_recommendation="Keep camera and transport boundaries explicit.",
            hardware_suggestion="Review the existing hardware references.",
            risk_analysis="Power and timing remain unverified.",
            next_action="Collect verified power evidence.",
            reference_ids=request.context.reference_ids,
            events=(event,),
        )
        return EngineeringResponse(
            **values,
            fingerprint=engineering_response_fingerprint(**values),
        )


def _client(product_sources):
    chat = EngineeringChatFake()
    repository = RepositoryFake()
    app = create_web_api_app(
        product_port=create_product_runtime().product_workspace_port(),
        preparation_port=PreparationFake(product_sources),
        repository_port=repository,
        attachment_port=AttachmentFake(),
        engineering_chat_port=chat,
        feedback_port=create_conversation_feedback_service().feedback_port(),
    )
    return TestClient(app), chat, repository


def test_project_chat_returns_structured_engineering_response(product_sources) -> None:
    client, chat, _ = _client(product_sources)
    client.post("/api/projects", json={"requirement": "Camera"})

    response = client.post(
        "/api/chat",
        json={
            "request_id": "chat-1",
            "project_id": "project-1",
            "message": "What architecture decision should be reviewed next?",
            "requested_at": _TIME.isoformat(),
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["project_id"] == "project-1"
    assert body["requirement_analysis"].startswith("The requirement")
    assert body["events"][0]["event_type"] == "COMPLETED"
    assert len(chat.calls) == 1
    assert chat.calls[0].context.project_id == "project-1"
    assert "payload" not in str(chat.calls[0].context.model_dump()).lower()


def test_feedback_endpoint_returns_projection_without_mutating_project(
    product_sources,
) -> None:
    client, _, repository = _client(product_sources)
    client.post("/api/projects", json={"requirement": "Camera"})
    before = repository.items["project-1"].model_dump(mode="json")

    response = client.post(
        "/api/feedback",
        json={
            "feedback_id": "feedback-1",
            "project_id": "project-1",
            "target_agent": "ENGINEERING_CHAT",
            "feedback_type": "CORRECT",
            "message": "Use the verified interface evidence.",
            "timestamp": _TIME.isoformat(),
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["event"]["event_type"] == "USER_FEEDBACK"
    assert set(body).isdisjoint({"message", "payload", "workspace"})
    assert repository.items["project-1"].model_dump(mode="json") == before


def test_project_chat_without_ai_binding_fails_safely(web_setup) -> None:
    client, _, _, _ = web_setup
    client.post("/api/projects", json={"requirement": "Camera"})

    response = client.post(
        "/api/chat",
        json={
            "request_id": "chat-1",
            "project_id": "project-1",
            "message": "Review the architecture.",
            "requested_at": _TIME.isoformat(),
        },
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "WEB_DEPENDENCY_UNAVAILABLE"
