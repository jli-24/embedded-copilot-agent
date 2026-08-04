from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.engineering_generation.contracts import (
    FirmwareArtifact,
    GenerationSnapshot,
    GenerationStatus,
)
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


class _Port:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    def get_snapshot(self, project_id: str):
        self.calls += 1
        return self.snapshot


def _client(port=None) -> TestClient:
    return TestClient(
        create_app(
            service=_ChatService(),
            settings=Settings(_env_file=None),
            generation_port=port,
        )
    )


def test_generation_route_is_unavailable_without_port() -> None:
    with _client() as client:
        response = client.get("/api/generation/project-1")
    assert response.status_code == 503
    assert response.json() == {"error": "GENERATION_UNAVAILABLE"}


def test_generation_route_returns_verified_projection_once() -> None:
    artifact = FirmwareArtifact.create(
        artifact_id="artifact-1",
        project_id="project-1",
        files=("main.c",),
        configuration=(),
        dependencies=(),
        summary="proposal",
    )
    port = _Port(
        GenerationSnapshot.create(
            project_id="project-1",
            status=GenerationStatus.REVIEW_REQUIRED,
            artifacts=(artifact,),
        )
    )
    with _client(port) as client:
        response = client.get("/api/generation/project-1")
    assert response.status_code == 200
    assert response.json()["artifacts"][0]["files"] == ["main.c"]
    assert "content" not in response.text
    assert port.calls == 1


def test_generation_route_rejects_unsafe_project_id() -> None:
    with _client() as client:
        response = client.get("/api/generation/../private")
    assert response.status_code in {404, 422}


def test_generation_route_sanitizes_invalid_port_result() -> None:
    with _client(_Port({"exception": "private"})) as client:
        response = client.get("/api/generation/project-1")
    assert response.status_code == 422
    assert response.json() == {"error": "GENERATION_SNAPSHOT_REJECTED"}
