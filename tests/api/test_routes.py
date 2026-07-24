from __future__ import annotations

import asyncio
from typing import Literal

import httpx
import pytest

from embedded_copilot.api.main import create_app
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.schemas.result import (
    ErrorCode,
    ErrorDetail,
    KnowledgeResult,
    SourceCitation,
)
from embedded_copilot.schemas.state import AgentName
from embedded_copilot.services.config import Settings


class FakeCopilotService:
    def __init__(
        self,
        *,
        outcome: Literal["success", "timeout", "exception"] = "success",
    ) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str]] = []

    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        self.calls.append((message, trace_id))
        if self.outcome == "exception":
            raise RuntimeError("private diagnostic detail")
        if self.outcome == "timeout":
            return ChatResponse(
                answer="",
                trace_id=trace_id,
                error=ErrorDetail(
                    code=ErrorCode.TIMEOUT,
                    message="Workflow timed out.",
                    retryable=True,
                ),
            )
        citation = SourceCitation(
            source="knowledge/embedded_basics.md",
            filename="embedded_basics.md",
            page=None,
            chunk_id="spi",
            score=0.9,
        )
        result = KnowledgeResult(answer="Grounded answer", sources=[citation])
        return ChatResponse(
            answer=result.answer,
            agents_used=[AgentName.KNOWLEDGE],
            sources=[citation],
            trace_id=trace_id,
            result=result,
        )


async def _request(
    service: FakeCopilotService,
    method: str,
    path: str,
    *,
    json: dict[str, str] | None = None,
) -> httpx.Response:
    app = create_app(service=service, settings=Settings(_env_file=None))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)


@pytest.mark.parametrize("path", ["/api/v1/chat", "/chat"])
def test_chat_paths_return_stable_envelope(path: str) -> None:
    service = FakeCopilotService()

    response = asyncio.run(
        _request(
            service,
            "POST",
            path,
            json={"message": "ESP32如何配置SPI？"},
        )
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agents_used"] == ["knowledge"]
    assert payload["sources"][0]["filename"] == "embedded_basics.md"
    assert payload["result"]["kind"] == "knowledge"
    assert payload["trace_id"] == response.headers["x-trace-id"]
    assert service.calls[0][0] == "ESP32如何配置SPI？"


@pytest.mark.parametrize("path", ["/api/v1/health", "/health"])
def test_health_paths_report_v0130(path: str) -> None:
    response = asyncio.run(
        _request(FakeCopilotService(), "GET", path)
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.13.0",
        "mode": "offline",
    }


def test_blank_message_uses_validation_error_envelope() -> None:
    service = FakeCopilotService()

    response = asyncio.run(
        _request(service, "POST", "/chat", json={"message": "   "})
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["trace_id"] == response.headers["x-trace-id"]
    assert service.calls == []


def test_timeout_maps_to_504() -> None:
    response = asyncio.run(
        _request(
            FakeCopilotService(outcome="timeout"),
            "POST",
            "/chat",
            json={"message": "ESP32 SPI"},
        )
    )

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "timeout"


def test_internal_error_does_not_expose_diagnostic_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR")
    response = asyncio.run(
        _request(
            FakeCopilotService(outcome="exception"),
            "POST",
            "/chat",
            json={"message": "ESP32 SPI"},
        )
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private diagnostic detail" not in response.text
    assert "private diagnostic detail" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
