from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from embedded_copilot.api.autonomous_models import (
    AgentExecutionView,
    ApprovalGateView,
    AutonomousLoopSnapshot,
    LoopStatus,
    RepairLoopView,
    TaskGraph,
    TaskGraphNode,
    TimelineStage,
    LoopTimelineItem,
    VerificationStatusView,
    ViewStatus,
)
from embedded_copilot.api.main import create_app
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


def _snapshot() -> AutonomousLoopSnapshot:
    return AutonomousLoopSnapshot.create(
        project_id="camera-project",
        status=LoopStatus.EXECUTING,
        progress=60,
        tasks=("firmware_build", "verification"),
        current_task="firmware_build",
        next_task="verification",
        timeline=(
            LoopTimelineItem(
                stage=TimelineStage.REQUIREMENT,
                status=ViewStatus.COMPLETED,
                label="Requirement",
            ),
            LoopTimelineItem(
                stage=TimelineStage.AGENT_EXECUTION,
                status=ViewStatus.RUNNING,
                label="Agent Execution",
                summary="Firmware agent is running",
            ),
        ),
        task_graph=TaskGraph(
            nodes=(
                TaskGraphNode(
                    node_id="firmware_build",
                    label="Firmware build",
                    status=ViewStatus.RUNNING,
                ),
                TaskGraphNode(
                    node_id="verification",
                    label="Verification",
                    status=ViewStatus.PENDING,
                ),
            ),
            edges=(),
        ),
        agents=(
            AgentExecutionView(
                agent_id="firmware",
                task_id="firmware_build",
                status=ViewStatus.RUNNING,
                summary="Building firmware",
            ),
        ),
        approval=ApprovalGateView(status=ViewStatus.APPROVED, reviewer="reviewer-1"),
        verification=VerificationStatusView(
            status=ViewStatus.PENDING, review_required=True
        ),
        repair=RepairLoopView(
            status=ViewStatus.NOT_REQUIRED, iteration=0, max_iterations=3
        ),
        updated_at=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
    )


class _Port:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def get_snapshot(self, project_id):
        self.calls += 1
        assert project_id == "camera-project"
        return self.value


def _client(port=None):
    return TestClient(
        create_app(
            service=_ChatService(),
            settings=Settings(_env_file=None),
            autonomous_loop_port=port,
        )
    )


def test_snapshot_success_is_safe_projection():
    port = _Port(_snapshot())
    with _client(port) as client:
        response = client.get("/api/autonomous/loop/camera-project")
    assert response.status_code == 200
    assert response.json()["project_id"] == "camera-project"
    assert "fingerprint" in response.json()
    assert "source_code" not in response.json()
    assert port.calls == 1


def test_missing_port_is_unavailable():
    with _client() as client:
        response = client.get("/api/autonomous/loop/camera-project")
    assert response.status_code == 503
    assert response.json() == {"error": "AUTONOMOUS_UNAVAILABLE"}


def test_missing_project_is_not_found():
    port = _Port(None)
    with _client(port) as client:
        response = client.get("/api/autonomous/loop/camera-project")
    assert response.status_code == 404
    assert response.json() == {"error": "AUTONOMOUS_PROJECT_NOT_FOUND"}


def test_invalid_snapshot_is_rejected_without_leaking_exception():
    port = _Port({"project_id": "camera-project", "exception": "private"})
    with _client(port) as client:
        response = client.get("/api/autonomous/loop/camera-project")
    assert response.status_code == 422
    assert response.json() == {"error": "AUTONOMOUS_SNAPSHOT_REJECTED"}


@pytest.mark.parametrize("project_id", ["../secret", "a/b", "a\\b", ""])
def test_unsafe_project_id_rejected(project_id: str):
    with _client(_Port(_snapshot())) as client:
        response = client.get(f"/api/autonomous/loop/{project_id}")
    assert response.status_code in {404, 422}
