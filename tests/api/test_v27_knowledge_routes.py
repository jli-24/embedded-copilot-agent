from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.knowledge_evolution.adapters.fake import (
    FakeKnowledgeEvolutionPort,
    FakeKnowledgeRetrievalPort,
)
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


def test_v27_routes_success_and_strict_query() -> None:
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        knowledge_port=FakeKnowledgeEvolutionPort(),
        retrieval_port=FakeKnowledgeRetrievalPort(),
    )
    with TestClient(app) as client:
        snapshot = client.get("/api/knowledge/v27/demo")
        query = client.post(
            "/api/knowledge/v27/query",
            json={
                "project_id": "demo",
                "requirement_reference": "requirement:demo",
                "context_fingerprint": snapshot.json()["fingerprint"],
            },
        )
        extra = client.post(
            "/api/knowledge/v27/query",
            json={
                "project_id": "demo",
                "requirement_reference": "requirement:demo",
                "context_fingerprint": snapshot.json()["fingerprint"],
                "extra": "forbidden",
            },
        )
    assert snapshot.status_code == 200
    assert query.status_code == 200
    assert query.json()[0]["confidence"] == "PROJECTED"
    assert extra.status_code == 422


def test_v27_routes_are_unavailable_without_ports() -> None:
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/knowledge/v27/demo").json() == {
            "error": "KNOWLEDGE_UNAVAILABLE"
        }
        assert client.post(
            "/api/knowledge/v27/query",
            json={
                "project_id": "demo",
                "requirement_reference": "requirement:demo",
                "context_fingerprint": "sha256:" + "0" * 64,
            },
        ).json() == {"error": "RETRIEVAL_UNAVAILABLE"}
