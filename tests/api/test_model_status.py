from __future__ import annotations

import asyncio

import httpx

from embedded_copilot.api.main import create_app
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="Existing chat.", trace_id=trace_id)


def test_model_status_endpoint_returns_only_safe_dto_fields() -> None:
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        workspace_service=None,
        experience_service=None,
    )

    async def request() -> httpx.Response:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/copilot/models/status")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json() == {
        "provider": "unavailable",
        "status": "unavailable",
        "capabilities": [],
        "model": None,
    }
    for forbidden in (
        "url",
        "endpoint",
        "prompt",
        "token",
        "credential",
        "history",
        "settings",
        "config",
    ):
        assert forbidden not in response.text.casefold()
