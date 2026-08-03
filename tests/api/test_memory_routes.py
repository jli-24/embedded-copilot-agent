from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from embedded_copilot.api.main import create_app
from embedded_copilot.knowledge_writer import KnowledgeWriteResult, KnowledgeWriteStatus
from embedded_copilot.memory_automation import (
    MemorySourceKind,
    MemorySourceProjection,
    VersionMemoryInput,
    create_memory_automation,
)
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings


class _Chat:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="ok", trace_id=trace_id)


class _MemoryPort:
    def __init__(self, candidate) -> None:
        self.candidate = candidate

    def list_candidates(self):
        return (self.candidate,)

    def get_candidate(self, memory_id: str):
        return self.candidate if memory_id == self.candidate.memory_id else None


class _Writer:
    def __init__(self) -> None:
        self.calls = 0

    def write(self, artifact):
        self.calls += 1
        return KnowledgeWriteResult(
            status=KnowledgeWriteStatus.CREATED,
            memory_id=artifact.memory_id,
            event_type="MEMORY_CREATED",
            message="Knowledge artifact written.",
        )


def test_memory_routes_project_and_approve_without_chat_changes() -> None:
    source = MemorySourceProjection(
        source_type=MemorySourceKind.BUILD_OBSERVATION,
        source_id="build-1",
        source_reference="build:1",
        source_fingerprint="sha256:" + "d" * 64,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    candidate = create_memory_automation().project(
        VersionMemoryInput(source=source, summary="Build passed")
    )
    writer = _Writer()
    app = create_app(
        settings=Settings(_env_file=None),
        service=_Chat(),
        workspace_service=None,
        experience_service=None,
        memory_port=_MemoryPort(candidate),
        memory_writer=writer,
    )

    async def exercise() -> tuple[httpx.Response, httpx.Response]:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                candidates = await client.get("/api/memory/candidates")
                approval = await client.post(
                    "/api/memory/approve",
                    json={
                        "memory_id": candidate.memory_id,
                        "candidate_fingerprint": candidate.fingerprint,
                        "reviewer": "reviewer-1",
                        "decision": "APPROVED",
                        "reviewed_at": "2026-01-02T00:00:00Z",
                    },
                )
                return candidates, approval

    candidates, approval = asyncio.run(exercise())
    assert candidates.status_code == 200
    assert candidates.json()["candidates"][0]["memory_id"] == candidate.memory_id
    assert approval.status_code == 200
    assert approval.json()["event_type"] == "MEMORY_CREATED"
    assert writer.calls == 1

