from __future__ import annotations

import asyncio

import httpx

from embedded_copilot.api.main import create_app
from embedded_copilot.engineering_intelligence import (
    ContextStage,
    EngineeringContextInputProjection,
    EngineeringIntelligenceRequest,
    EngineeringIntelligenceResponse,
    EvidenceSourceType,
    EvidenceTrustBasis,
    build_evidence,
    build_recommendation,
    fuse_evidence,
)
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings


class _Chat:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="ok", trace_id=trace_id)


class _Context:
    def __init__(self, value: EngineeringContextInputProjection) -> None:
        self.value = value
        self.calls = 0

    def get_context(self, project_id: str):
        self.calls += 1
        return self.value if project_id == self.value.project_id else None


class _Intelligence:
    async def query(
        self, request: EngineeringIntelligenceRequest
    ) -> EngineeringIntelligenceResponse:
        snapshot = request.context_snapshot
        evidence = build_evidence(
            evidence_id="local-e-1",
            source_type=EvidenceSourceType.LOCAL_KNOWLEDGE,
            trust_basis=EvidenceTrustBasis.PROJECTED,
            summary="SPI guidance",
            reference_id="knowledge-1",
            confidence=0.5,
            source_rank=0,
        )
        knowledge = fuse_evidence((evidence,))
        return EngineeringIntelligenceResponse(
            recommendation=build_recommendation(snapshot, knowledge),
            knowledge_context=knowledge,
            query_fingerprint="sha256:" + "a" * 64,
        )


def _context() -> EngineeringContextInputProjection:
    return EngineeringContextInputProjection(
        project_id="project-1",
        project_name="Board",
        stage=ContextStage.PCB_DESIGN,
        decision_topic="interface",
        constraints=(),
    )


def test_intelligence_routes_read_context_once_and_keep_existing_chat_boundary() -> (
    None
):
    context = _Context(_context())
    app = create_app(
        settings=Settings(_env_file=None),
        service=_Chat(),
        workspace_service=None,
        intelligence_port=_Intelligence(),
        intelligence_context_port=context,
    )

    async def exercise() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                query = await client.post(
                    "/api/intelligence/query",
                    json={
                        "project_id": "project-1",
                        "question": "Which interface should be reviewed?",
                    },
                )
                snapshot = await client.get("/api/intelligence/context/project-1")
                missing = await client.get("/api/intelligence/context/missing")
                return query, snapshot, missing

    query, snapshot, missing = asyncio.run(exercise())
    assert query.status_code == 200
    assert query.json()["result"]["recommendation"]["review_required"] is True
    assert "payload" not in query.text
    assert snapshot.status_code == 200
    assert snapshot.json()["context"]["project_id"] == "project-1"
    assert missing.status_code == 404
    assert context.calls == 3


def test_intelligence_dependency_error_is_fixed() -> None:
    app = create_app(
        settings=Settings(_env_file=None), service=_Chat(), workspace_service=None
    )

    async def exercise() -> httpx.Response:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.post(
                    "/api/intelligence/query",
                    json={"project_id": "project-1", "question": "review"},
                )

    response = asyncio.run(exercise())
    assert response.status_code == 503
    assert response.json() == {"error": "INTELLIGENCE_DEPENDENCY_UNAVAILABLE"}
