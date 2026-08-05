from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.debug_analysis.adapters.fake import FakeDebugAnalysisPort
from embedded_copilot.optimization.adapters.fake import FakeOptimizationPort
from embedded_copilot.optimization.contracts import OptimizationApprovalRequest
from embedded_copilot.optimization.contracts import OptimizationStatus
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


class _Approval:
    def __init__(self, proposal_port: FakeOptimizationPort) -> None:
        self.proposal_port = proposal_port
        self.calls = 0

    def approve(self, request: OptimizationApprovalRequest):
        self.calls += 1
        proposal = self.proposal_port.get_snapshot(request.proposal_id.split(":")[1])
        assert proposal is not None
        assert request.proposal_fingerprint == proposal.fingerprint
        return proposal.model_copy(update={"status": OptimizationStatus.APPROVED, "fingerprint": "sha256:" + "0" * 64})

    def reject(self, request: OptimizationApprovalRequest):
        self.calls += 1
        return self.proposal_port.get_snapshot(request.proposal_id.split(":")[1])


def test_v23_debug_and_optimization_success() -> None:
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        debug_analysis_port=FakeDebugAnalysisPort(),
        optimization_port=FakeOptimizationPort(),
    )
    with TestClient(app) as client:
        debug = client.get("/api/debug/v23/demo")
        optimization = client.get("/api/optimization/v23/demo")
    assert debug.status_code == 200
    assert optimization.status_code == 200
    assert optimization.json()["confidence"] == "PROJECTED"
    assert "summary" in debug.json()["findings"][0]


def test_v23_ports_missing_and_invalid_are_safe() -> None:
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/debug/v23/demo").json() == {"error": "DEBUG_UNAVAILABLE"}
        assert client.get("/api/optimization/v23/demo").json() == {"error": "OPTIMIZATION_UNAVAILABLE"}
        assert client.get("/api/debug/v23/../secret").status_code in {404, 422}


def test_approval_requires_binding_and_calls_once() -> None:
    proposal_port = FakeOptimizationPort()
    proposal = proposal_port.get_snapshot("demo")
    assert proposal is not None
    approval = _Approval(proposal_port)
    app = create_app(
        service=_ChatService(), settings=Settings(_env_file=None), optimization_approval_port=approval
    )
    body = {
        "proposal_id": proposal.proposal_id,
        "proposal_fingerprint": proposal.fingerprint,
        "reviewer": "reviewer",
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    with TestClient(app) as client:
        response = client.post(f"/api/optimization/v23/{proposal.proposal_id}/approve", json=body)
    assert response.status_code == 422
    assert response.json() == {"error": "PROPOSAL_REJECTED"}
    assert approval.calls == 1
