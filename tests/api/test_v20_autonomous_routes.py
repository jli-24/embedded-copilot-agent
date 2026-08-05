from __future__ import annotations

from fastapi.testclient import TestClient
from embedded_copilot.approval_gate.contracts import ApprovalStatus
from embedded_copilot.autonomous_loop.contracts import (
    AutonomousLoopSnapshot,
    LoopStage,
    LoopTimelineItem,
)

from embedded_copilot.api.main import create_app
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


class _Coordinator:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    def get_snapshot(self, project_id):
        self.calls += 1
        return self.snapshot


def _snapshot() -> AutonomousLoopSnapshot:
    return AutonomousLoopSnapshot.create(
        project_id="demo",
        loop_id="loop-1",
        current_stage=LoopStage.INITIALIZING,
        completed_stages=(),
        pending_action=None,
        approval_status=ApprovalStatus.PENDING,
        iteration=0,
        timeline=(
            LoopTimelineItem(
                stage=LoopStage.INITIALIZING, status="RUNNING", label="Initializing"
            ),
        ),
    )


def test_v20_routes_are_unavailable_without_coordinator() -> None:
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/v2/autonomous/loop/demo").json() == {
            "error": "AUTONOMOUS_UNAVAILABLE"
        }
        assert client.post("/api/autonomous/loop/demo/resume").json() == {
            "error": "AUTONOMOUS_UNAVAILABLE"
        }
        assert client.post("/api/autonomous/action/action-1/approve").json() == {
            "error": "AUTONOMOUS_UNAVAILABLE"
        }
        assert client.post("/api/autonomous/action/action-1/reject").json() == {
            "error": "AUTONOMOUS_UNAVAILABLE"
        }


def test_v20_get_returns_verified_snapshot_once() -> None:
    coordinator = _Coordinator(_snapshot())
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        loop_coordinator_port=coordinator,
    )
    with TestClient(app) as client:
        response = client.get("/api/v2/autonomous/loop/demo")
    assert response.status_code == 200
    assert response.json()["current_stage"] == "INITIALIZING"
    assert coordinator.calls == 1
