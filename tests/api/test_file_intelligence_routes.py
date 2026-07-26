from __future__ import annotations

import asyncio

import httpx
import pytest

from embedded_copilot.api.main import create_app
from embedded_copilot.file_runtime import (
    FileAnalysisTimeout,
    FileIntelligenceResponse,
    FileReferenceConflict,
    FileReferenceNotFound,
    FileReferenceRequest,
    FileRuntimeUnavailable,
    FileType,
)
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="Existing chat.", trace_id=trace_id)


class _FilePort:
    def __init__(self, outcome: object | None = None) -> None:
        self.outcome = outcome
        self.request: FileReferenceRequest | None = None

    async def analyze(
        self,
        request: FileReferenceRequest,
    ) -> FileIntelligenceResponse:
        self.request = request
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FileIntelligenceResponse(
            summary="SOURCE_CODE file structure: 12 lines, 240 characters."
        )


async def _request(
    *,
    port: _FilePort | None,
    json: dict[str, object],
) -> httpx.Response:
    app = create_app(
        service=_ChatService(),
        workspace_service=None,
        experience_service=None,
        vision_port=None,
        file_port=port,
        settings=Settings(_env_file=None),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/api/v1/copilot/sessions/session:1/files/analyze",
                json=json,
            )


def _payload() -> dict[str, object]:
    return {
        "file_id": "file:1",
        "instruction_summary": "Inspect the referenced source structure.",
    }


def test_file_analysis_route_maps_public_contract_to_model_agnostic_port() -> None:
    port = _FilePort()

    response = asyncio.run(_request(port=port, json=_payload()))

    assert response.status_code == 200
    assert response.json() == {
        "type": "reasoning_suggestion",
        "summary": "SOURCE_CODE file structure: 12 lines, 240 characters.",
        "review_required": True,
    }
    assert port.request == FileReferenceRequest(
        session_id="session:1",
        file_id="file:1",
        file_type=FileType.UNKNOWN,
        instruction_summary="Inspect the referenced source structure.",
    )


@pytest.mark.parametrize("field", ("path", "content", "file_url", "size"))
def test_file_analysis_route_rejects_infrastructure_fields(field: str) -> None:
    payload = _payload()
    payload[field] = r"C:\workspace\private\main.py"

    response = asyncio.run(_request(port=_FilePort(), json=payload))

    assert response.status_code == 422
    assert "workspace" not in response.text
    assert "main.py" not in response.text


@pytest.mark.parametrize(
    ("error", "expected_status"),
    (
        (FileReferenceNotFound(), 404),
        (FileReferenceConflict(), 409),
        (FileRuntimeUnavailable(), 503),
        (FileAnalysisTimeout(), 504),
    ),
)
def test_file_analysis_route_maps_runtime_errors_without_details(
    error: Exception,
    expected_status: int,
) -> None:
    response = asyncio.run(_request(port=_FilePort(error), json=_payload()))

    assert response.status_code == expected_status
    assert response.json()["error"] == "file_unavailable"
    assert set(response.json()) == {"error", "trace_id"}
    assert "filename" not in response.text.casefold()
    assert "path" not in response.text.casefold()
    assert "traceback" not in response.text.casefold()


def test_file_analysis_route_is_unavailable_without_injected_port() -> None:
    response = asyncio.run(_request(port=None, json=_payload()))

    assert response.status_code == 503
    assert response.json()["error"] == "file_unavailable"
