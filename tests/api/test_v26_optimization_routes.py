from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.engineering_optimization.adapters.fake import (
    FakeOptimizationAnalysisPort,
    FakeOptimizationApprovalPort,
)
from embedded_copilot.digital_twin.adapters.fake import FakeDigitalTwinAdapter
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


def test_v26_routes_success_and_approval_identity() -> None:
    analysis = FakeOptimizationAnalysisPort()
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        digital_twin_port=FakeDigitalTwinAdapter(),
        optimization_analysis_port=analysis,
        optimization_approval_port=FakeOptimizationApprovalPort(),
    )
    with TestClient(app) as client:
        twin = client.get("/api/digital-twin/v26/demo")
        result = client.get("/api/optimization/v26/demo")
        finding = result.json()["findings"][0]
        decision = client.post(
            f"/api/optimization/v26/{finding['finding_id']}/approve",
            json={
                "finding_id": finding["finding_id"],
                "finding_fingerprint": finding["fingerprint"],
                "reviewer": "reviewer:demo",
                "decided_at": "2026-01-01T00:00:00Z",
            },
        )
    assert twin.status_code == 200
    assert result.status_code == 200
    assert decision.status_code == 200
    assert decision.json()["status"] == "APPROVED"


def test_v26_routes_are_unavailable_without_ports() -> None:
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/digital-twin/v26/demo").json() == {
            "error": "DIGITAL_TWIN_UNAVAILABLE"
        }
        assert client.get("/api/optimization/v26/demo").json() == {
            "error": "OPTIMIZATION_UNAVAILABLE"
        }

