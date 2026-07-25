from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from embedded_copilot.api.main import create_app
from embedded_copilot.integration.report import EngineeringReport
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.analysis import AnalysisService
from embedded_copilot.services.config import Settings
from embedded_copilot.supervisor.agent import SupervisorAgent
from web.demo import load_demo_manifest


class _LegacyChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="legacy", trace_id=trace_id)


def test_product_demo_runs_manifest_through_api_and_supervisor() -> None:
    async def scenario() -> None:
        manifest = load_demo_manifest(Path("demo/esp32_camera/manifest.json"))
        analysis = AnalysisService(
            supervisor=SupervisorAgent(),
            timeout_seconds=5,
            execution_id_factory=lambda: "product-demo-1",
        )
        app = create_app(
            settings=Settings(_env_file=None),
            service=_LegacyChatService(),
            analysis_service=analysis,
        )
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/analyze",
                    json={
                        "request": manifest.request,
                        "attachments": [
                            item.model_dump(mode="json")
                            for item in manifest.attachments
                        ],
                        "options": {
                            "required_agents": list(manifest.required_agents)
                        },
                    },
                )
                assert response.status_code == 202
                for _ in range(100):
                    status = await client.get(
                        "/api/v1/status/product-demo-1"
                    )
                    if status.json()["status"] in {"completed", "failed"}:
                        break
                    await asyncio.sleep(0.01)
                assert status.json()["status"] == "completed"
                report_response = await client.get(
                    "/api/v1/report/product-demo-1"
                )
                report = EngineeringReport.model_validate(
                    report_response.json()
                )

        assert report.hardware_section is not None
        assert report.firmware_section is not None
        assert report.pcb_section is not None
        assert report.debug_section is None
        assert report.summary.succeeded == 3
        assert report.summary.failed == 1
        assert any(
            event.source_agent == "DebugAgent" and event.status == "error"
            for event in report.trace
        )
        assert all(event.source_agent and event.source_id for event in report.trace)
        serialized = report.model_dump_json()
        assert "UnifiedPCBModel" not in serialized
        assert "UnifiedDatasheetModel" not in serialized
        assert "camera_firmware.c" not in serialized
        assert "undefined reference" not in serialized

    asyncio.run(scenario())
