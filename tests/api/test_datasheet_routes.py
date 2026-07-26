from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

import embedded_copilot.api.main as api_main
from embedded_copilot.api.main import create_app
from embedded_copilot.datasheet_runtime import (
    DatasheetAnalysisTimeout,
    DatasheetDocumentRejected,
    DatasheetRequest,
    DatasheetResponse,
    DatasheetRuntimeUnavailable,
    DatasheetSummary,
)
from embedded_copilot.file_runtime import (
    FileAnalysisTimeout,
    FileReferenceConflict,
    FileReferenceNotFound,
    FileRuntimeUnavailable,
)
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="Existing chat.", trace_id=trace_id)


class _AnalysisService:
    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _DatasheetPort:
    def __init__(self, outcome: object | None = None) -> None:
        self.outcome = outcome
        self.request: DatasheetRequest | None = None

    async def analyze(self, request: DatasheetRequest) -> DatasheetResponse:
        self.request = request
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return DatasheetResponse(
            summary=DatasheetSummary(
                file_id=request.file_id,
                component_candidate={
                    "semantics": "candidate",
                    "family": "STM32",
                    "model": "STM32F103C8T6",
                },
                interface_candidates=(
                    {"semantics": "candidate", "name": "SPI"},
                    {"semantics": "candidate", "name": "I2C"},
                ),
                electrical_candidates=(
                    {
                        "semantics": "candidate",
                        "kind": "voltage_range",
                        "minimum": 2.0,
                        "maximum": 3.6,
                        "unit": "V",
                    },
                ),
                section_candidates=(
                    {
                        "semantics": "candidate",
                        "name": "Electrical Characteristics",
                    },
                ),
            )
        )


async def _request(
    *,
    port: _DatasheetPort | None,
    json: dict[str, object],
    session_id: str = "session:1",
) -> httpx.Response:
    app = create_app(
        service=_ChatService(),
        analysis_service=_AnalysisService(),
        workspace_service=None,
        experience_service=None,
        vision_port=None,
        file_port=None,
        datasheet_port=port,
        settings=Settings(_env_file=None),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                f"/api/v1/copilot/sessions/{session_id}/datasheets/analyze",
                json=json,
            )


def _payload() -> dict[str, object]:
    return {
        "file_id": "file:1",
        "instruction_summary": "Extract unverified datasheet candidates.",
    }


def test_datasheet_route_returns_only_structured_candidate_contract() -> None:
    port = _DatasheetPort()

    response = asyncio.run(_request(port=port, json=_payload()))

    assert response.status_code == 200
    assert response.json() == {
        "type": "reasoning_suggestion",
        "summary": {
            "candidate_semantics": "unverified",
            "file_id": "file:1",
            "component_candidate": {
                "semantics": "candidate",
                "family": "STM32",
                "model": "STM32F103C8T6",
            },
            "interface_candidates": [
                {"semantics": "candidate", "name": "SPI"},
                {"semantics": "candidate", "name": "I2C"},
            ],
            "electrical_candidates": [
                {
                    "semantics": "candidate",
                    "kind": "voltage_range",
                    "minimum": 2.0,
                    "maximum": 3.6,
                    "unit": "V",
                }
            ],
            "section_candidates": [
                {
                    "semantics": "candidate",
                    "name": "Electrical Characteristics",
                }
            ],
        },
        "review_required": True,
    }
    assert port.request == DatasheetRequest(
        session_id="session:1",
        file_id="file:1",
        instruction_summary="Extract unverified datasheet candidates.",
    )
    assert "engineering_fact" not in response.text.casefold()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("path", r"C:\private\datasheet.pdf"),
        ("content", "PRIVATE_PDF_TEXT"),
        ("file_url", "file:///private/datasheet.pdf"),
        ("provider", "private-provider"),
        ("model", "private-model"),
        ("credential", "private-secret"),
    ),
)
def test_datasheet_route_rejects_infrastructure_fields(
    field: str,
    value: str,
) -> None:
    payload = _payload()
    payload[field] = value

    response = asyncio.run(_request(port=_DatasheetPort(), json=payload))

    assert response.status_code == 422
    assert set(response.json()) == {"error", "trace_id"}
    assert response.json()["error"] == "datasheet_unavailable"
    assert value not in response.text


@pytest.mark.parametrize(
    "session_id",
    (
        "invalid session",
        "session@private",
        "C:%5Cprivate%5Cdatasheet.pdf",
    ),
)
def test_datasheet_route_rejects_unsafe_path_session_id(session_id: str) -> None:
    response = asyncio.run(
        _request(
            port=_DatasheetPort(),
            json=_payload(),
            session_id=session_id,
        )
    )

    assert response.status_code == 422
    assert set(response.json()) == {"error", "trace_id"}
    assert response.json()["error"] == "datasheet_unavailable"


@pytest.mark.parametrize(
    ("error", "expected_status"),
    (
        (FileReferenceNotFound(), 404),
        (FileReferenceConflict(), 409),
        (DatasheetDocumentRejected(), 422),
        (DatasheetRuntimeUnavailable(), 503),
        (FileRuntimeUnavailable(), 503),
        (DatasheetAnalysisTimeout(), 504),
        (FileAnalysisTimeout(), 504),
    ),
)
def test_datasheet_route_maps_runtime_errors_without_details(
    error: Exception,
    expected_status: int,
) -> None:
    response = asyncio.run(_request(port=_DatasheetPort(error), json=_payload()))

    assert response.status_code == expected_status
    assert response.json()["error"] == "datasheet_unavailable"
    assert set(response.json()) == {"error", "trace_id"}
    assert "filename" not in response.text.casefold()
    assert "path" not in response.text.casefold()
    assert "traceback" not in response.text.casefold()


def test_datasheet_route_is_unavailable_without_injected_port() -> None:
    response = asyncio.run(_request(port=None, json=_payload()))

    assert response.status_code == 503
    assert response.json()["error"] == "datasheet_unavailable"


def test_default_bootstrap_composes_file_and_datasheet_ports_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_intelligence_port = object()
    extraction_port = object()
    datasheet_port = object()
    file_runtime = SimpleNamespace(
        file_port=lambda: file_intelligence_port,
        extraction_port=lambda: extraction_port,
    )
    create_file_calls: list[tuple[object, object]] = []
    create_datasheet_calls: list[object] = []

    def fake_create_file_runtime(settings: object, catalog: object) -> object:
        create_file_calls.append((settings, catalog))
        return file_runtime

    def fake_create_datasheet_runtime(port: object) -> object:
        create_datasheet_calls.append(port)
        return SimpleNamespace(datasheet_port=lambda: datasheet_port)

    monkeypatch.setattr(
        api_main,
        "build_experience_runtime",
        lambda **kwargs: SimpleNamespace(
            workspace_service=None,
            experience_service=None,
            attachment_repository=object(),
        ),
    )
    monkeypatch.setattr(api_main, "create_file_runtime", fake_create_file_runtime)
    monkeypatch.setattr(
        api_main,
        "create_datasheet_runtime",
        fake_create_datasheet_runtime,
    )

    async def exercise() -> None:
        app = create_app(
            service=_ChatService(),
            analysis_service=_AnalysisService(),
            vision_port=None,
            settings=Settings(_env_file=None),
        )
        async with app.router.lifespan_context(app):
            assert app.state.file_port is file_intelligence_port
            assert app.state.datasheet_port is datasheet_port

    asyncio.run(exercise())

    assert len(create_file_calls) == 1
    assert create_datasheet_calls == [extraction_port]
