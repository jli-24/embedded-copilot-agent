from __future__ import annotations

import asyncio
from typing import Literal

import httpx

from embedded_copilot.api.main import create_app
from embedded_copilot.integration.context import IntegrationTraceEvent
from embedded_copilot.integration.report import EngineeringReport, ReportSummary
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.analysis import AnalysisCommand
from embedded_copilot.services.config import Settings
from embedded_copilot.services.execution import (
    ExecutionCapacityError,
    ExecutionNotFoundError,
    ExecutionSnapshot,
    ReportNotReadyError,
)


def _report() -> EngineeringReport:
    source_id = "supervisor:engineering-report"
    return EngineeringReport(
        summary=ReportSummary(
            text="Execution completed.",
            succeeded=0,
            failed=0,
            source_agent="SupervisorAgent",
            source_id=source_id,
        ),
        trace=(
            IntegrationTraceEvent(
                sequence=1,
                stage="report_aggregated",
                status="success",
                source_agent="SupervisorAgent",
                source_id=source_id,
            ),
        ),
    )


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="legacy", trace_id=trace_id)


class _AnalysisService:
    def __init__(self, outcome: Literal["ok", "full"] = "ok") -> None:
        self.outcome = outcome
        self.commands: list[AnalysisCommand] = []
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.started = False

    async def submit(self, command: AnalysisCommand) -> ExecutionSnapshot:
        if self.outcome == "full":
            raise ExecutionCapacityError
        self.commands.append(command)
        return ExecutionSnapshot(execution_id="exec-1", status="queued")

    def get_status(self, execution_id: str) -> ExecutionSnapshot:
        if execution_id == "missing":
            raise ExecutionNotFoundError
        return ExecutionSnapshot(execution_id=execution_id, status="completed")

    def get_report(self, execution_id: str) -> EngineeringReport:
        if execution_id == "missing":
            raise ExecutionNotFoundError
        if execution_id == "pending":
            raise ReportNotReadyError
        return _report()


async def _request(
    analysis: _AnalysisService,
    method: str,
    path: str,
    *,
    json: object | None = None,
) -> httpx.Response:
    app = create_app(
        settings=Settings(_env_file=None),
        service=_ChatService(),
        analysis_service=analysis,
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)


def _payload() -> dict[str, object]:
    return {
        "request": "Review ESP32 camera firmware.",
        "attachments": [
            {
                "id": "source-1",
                "filename": "camera.c",
                "media_type": "source_code",
                "content_type": "text/x-c",
                "size_bytes": 128,
                "metadata": {"category": "source_code", "format": "c"},
            }
        ],
        "options": {"required_agents": ["firmware", "debug"]},
    }


def test_analyze_accepts_metadata_only_json_and_returns_202() -> None:
    analysis = _AnalysisService()
    response = asyncio.run(_request(analysis, "POST", "/api/v1/analyze", json=_payload()))

    assert response.status_code == 202
    assert response.json() == {"execution_id": "exec-1", "status": "queued"}
    command = analysis.commands[0]
    assert command.required_agents == ("firmware", "debug")
    assert command.input_context.attachments[0].filename == "camera.c"


def test_analyze_rejects_mime_mismatch_and_more_than_eight_attachments() -> None:
    mismatch = _payload()
    mismatch["attachments"][0]["content_type"] = "application/pdf"  # type: ignore[index]
    response = asyncio.run(
        _request(_AnalysisService(), "POST", "/api/v1/analyze", json=mismatch)
    )
    assert response.status_code == 422

    oversized = _payload()
    oversized["attachments"] = oversized["attachments"] * 9  # type: ignore[operator]
    response = asyncio.run(
        _request(_AnalysisService(), "POST", "/api/v1/analyze", json=oversized)
    )
    assert response.status_code == 422


def test_status_and_report_use_stable_http_semantics() -> None:
    assert asyncio.run(
        _request(_AnalysisService(), "GET", "/api/v1/status/exec-1")
    ).json()["status"] == "completed"
    assert asyncio.run(
        _request(_AnalysisService(), "GET", "/api/v1/report/exec-1")
    ).json() == _report().model_dump(mode="json")
    assert asyncio.run(
        _request(_AnalysisService(), "GET", "/api/v1/status/missing")
    ).status_code == 404
    assert asyncio.run(
        _request(_AnalysisService(), "GET", "/api/v1/report/pending")
    ).status_code == 409
    assert asyncio.run(
        _request(_AnalysisService(outcome="full"), "POST", "/api/v1/analyze", json=_payload())
    ).status_code == 503
