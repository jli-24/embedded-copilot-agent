from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.engineering_completion.adapters.fake import (
    FakeEngineeringCompletionPort,
)
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


def _app(port=None):
    return create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        engineering_completion_port=port,
    )


def test_v28_get_and_validate_success() -> None:
    with TestClient(_app(FakeEngineeringCompletionPort())) as client:
        response = client.get("/api/engineering/v28/demo")
        result = client.post(
            "/api/engineering/v28/validate",
            json={
                "project_id": "demo",
                "completion_snapshot": response.json(),
                "context_fingerprint": response.json()["fingerprint"],
            },
        )
    assert response.status_code == 200
    assert result.status_code == 200
    assert result.json()["status"] == "VALID"
    assert "reason" not in result.json()


def test_v28_missing_port_and_not_found_are_safe() -> None:
    with TestClient(_app()) as client:
        unavailable = client.get("/api/engineering/v28/demo")
        rejected = client.get("/api/engineering/v28/../bad")
    assert unavailable.status_code == 503
    assert unavailable.json() == {"error": "ENGINEERING_COMPLETION_UNAVAILABLE"}
    assert rejected.status_code in {404, 422}


def test_v28_validate_rejects_project_mismatch_and_extra_fields() -> None:
    with TestClient(_app(FakeEngineeringCompletionPort())) as client:
        snapshot = client.get("/api/engineering/v28/demo").json()
        mismatch = client.post(
            "/api/engineering/v28/validate",
            json={
                "project_id": "other",
                "completion_snapshot": snapshot,
                "context_fingerprint": snapshot["fingerprint"],
            },
        )
        extra = client.post(
            "/api/engineering/v28/validate",
            json={
                "project_id": "demo",
                "completion_snapshot": snapshot,
                "context_fingerprint": snapshot["fingerprint"],
                "extra": "forbidden",
            },
        )
    assert mismatch.status_code == 422
    assert mismatch.json() == {"error": "QUERY_REJECTED"}
    assert extra.status_code == 422
