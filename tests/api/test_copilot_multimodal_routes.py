from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from embedded_copilot.api.main import create_app
from embedded_copilot.conversation.models import ConversationMessage, ConversationTurn
from embedded_copilot.copilot.workspace import ProjectWorkspace
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    AttachmentBindingNotFound,
)
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings
from embedded_copilot.vision_runtime import VisionRequest, VisionResponse
from embedded_copilot.vision_runtime.gateway import VisionReferenceConflict
from embedded_copilot.vision_runtime.providers import (
    VisionProviderTimeout,
    VisionProviderUnavailable,
)

CREATED = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="Existing chat.", trace_id=trace_id)


class _WorkspaceService:
    def __init__(self) -> None:
        self.binding: AttachmentBinding | None = None

    async def create_session(self, **kwargs: object) -> ProjectWorkspace:
        raise AssertionError("not used")

    def get_session(self, **kwargs: object) -> ProjectWorkspace:
        raise AssertionError("not used")

    async def send_message(
        self,
        message: ConversationMessage,
        *,
        trace_id: str,
    ) -> ConversationTurn:
        raise AssertionError("not used")

    def bind_attachment(
        self,
        binding: AttachmentBinding,
        *,
        trace_id: str,
    ) -> AttachmentBinding:
        self.binding = binding
        return binding


class _VisionPort:
    def __init__(self, *, outcome: str = "success") -> None:
        self.outcome = outcome
        self.request: VisionRequest | None = None

    async def analyze(self, request: VisionRequest) -> VisionResponse:
        self.request = request
        error = {
            "missing": AttachmentBindingNotFound("PRIVATE_REFERENCE"),
            "conflict": VisionReferenceConflict("PRIVATE_CONFLICT"),
            "unavailable": VisionProviderUnavailable("PRIVATE_PROVIDER"),
            "timeout": VisionProviderTimeout("PRIVATE_TIMEOUT"),
        }.get(self.outcome)
        if error is not None:
            raise error
        return VisionResponse(
            summary="The reference metadata requires engineer review."
        )


async def _request(
    method: str,
    path: str,
    *,
    service: _WorkspaceService,
    vision_port: _VisionPort | None = None,
    json: dict[str, object],
) -> httpx.Response:
    app = create_app(
        service=_ChatService(),
        workspace_service=service,
        vision_port=vision_port or _VisionPort(),
        settings=Settings(_env_file=None),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)


def _attachment_payload() -> dict[str, object]:
    return {
        "reference_id": "image:1",
        "type": "IMAGE",
        "basename": "schematic.png",
        "summary": "ESP32 schematic image reference.",
        "size_bytes": 1024,
        "created_at": CREATED.isoformat(),
    }


def test_attachment_and_vision_routes_return_suggestion_only_contracts() -> None:
    service = _WorkspaceService()
    vision_port = _VisionPort()

    attachment = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions/session:1/attachments",
            service=service,
            json=_attachment_payload(),
        )
    )
    vision = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions/session:1/vision",
            service=service,
            vision_port=vision_port,
            json={
                "reference_id": "image:1",
                "instruction_summary": "Review the referenced schematic.",
            },
        )
    )

    assert attachment.status_code == 201
    assert attachment.json() == {
        "session_id": "session:1",
        "reference_id": "image:1",
        "type": "IMAGE",
        "basename": "schematic.png",
        "summary": "ESP32 schematic image reference.",
        "size_bytes": 1024,
        "status": "REFERENCED",
        "created_at": CREATED.isoformat().replace("+00:00", "Z"),
    }
    assert service.binding is not None
    assert vision.status_code == 200
    assert vision.json() == {
        "type": "reasoning_suggestion",
        "summary": "The reference metadata requires engineer review.",
        "review_required": True,
    }
    assert vision_port.request == VisionRequest(
        session_id="session:1",
        reference_id="image:1",
        image_type="unknown",
        instruction_summary="Review the referenced schematic.",
    )
    assert "artifact_update" not in vision.text


def test_attachment_route_rejects_binary_and_extra_content() -> None:
    payload = _attachment_payload()
    payload["content"] = "PRIVATE_FILE_CONTENT"

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions/session:1/attachments",
            service=_WorkspaceService(),
            json=payload,
        )
    )

    assert response.status_code == 422
    assert "PRIVATE_FILE_CONTENT" not in response.text


def test_attachment_route_rejects_text_as_an_attachment_type() -> None:
    payload = _attachment_payload()
    payload["type"] = "TEXT"

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions/session:1/attachments",
            service=_WorkspaceService(),
            json=payload,
        )
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed."


@pytest.mark.parametrize(
    ("outcome", "expected_status"),
    (
        ("missing", 404),
        ("conflict", 409),
        ("unavailable", 503),
        ("timeout", 504),
    ),
)
def test_multimodal_routes_map_safe_errors(
    outcome: str,
    expected_status: int,
) -> None:
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/copilot/sessions/session:1/vision",
            service=_WorkspaceService(),
            vision_port=_VisionPort(outcome=outcome),
            json={
                "reference_id": "image:1",
                "instruction_summary": "Review the referenced schematic.",
            },
        )
    )

    assert response.status_code == expected_status
    assert "PRIVATE_" not in response.text


def test_default_runtime_shares_attachment_reference_with_vision_runtime() -> None:
    async def exercise() -> tuple[
        httpx.Response,
        httpx.Response,
        httpx.Response,
        httpx.Response,
    ]:
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
                        "session_id": "session:shared",
                        "project_name": "Shared Reference Workspace",
                        "user_requirement": "Review reference metadata only.",
                        "created_at": CREATED.isoformat(),
                    },
                )
                bound = await client.post(
                    "/api/v1/copilot/sessions/session:shared/attachments",
                    json={
                        **_attachment_payload(),
                        "created_at": datetime(
                            2026,
                            7,
                            26,
                            12,
                            1,
                            tzinfo=timezone.utc,
                        ).isoformat(),
                    },
                )
                files = await client.get(
                    "/api/v1/copilot/sessions/session:shared/files"
                )
                vision = await client.post(
                    "/api/v1/copilot/sessions/session:shared/vision",
                    json={
                        "reference_id": "image:1",
                        "instruction_summary": "Review the reference metadata.",
                    },
                )
                return created, bound, files, vision

    created, bound, files, vision = asyncio.run(exercise())

    assert created.status_code == 201
    assert bound.status_code == 201
    assert files.status_code == 200
    assert vision.status_code == 503
    assert "provider" not in vision.text.casefold()
    assert files.json()["files"] == [
        {
            "file_id": "image:1",
            "basename": "schematic.png",
            "file_type": "OTHER",
            "size": 1024,
            "source": "INPUT",
            "status": "REFERENCED",
            "timestamp": "2026-07-26T12:01:00Z",
        }
    ]
