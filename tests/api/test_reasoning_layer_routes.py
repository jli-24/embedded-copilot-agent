from __future__ import annotations

import asyncio

import httpx

from embedded_copilot.api.main import create_app
from embedded_copilot.core.config import Settings
from embedded_copilot.engineering_intelligence import (
    ContextStage,
    EngineeringContextInputProjection,
    EvidenceSourceType,
    EvidenceTrustBasis,
    build_context_snapshot,
    build_evidence,
    build_recommendation,
    fuse_evidence,
)
from embedded_copilot.reasoning import (
    ReasoningEvidenceReference,
    ReasoningInputProjection,
)
from embedded_copilot.reasoning.adapters.fake import FakeReasoningPort


class _Resolver:
    def __init__(self, projection: ReasoningInputProjection) -> None:
        self.projection = projection

    def resolve(self, recommendation_id: str) -> ReasoningInputProjection | None:
        if recommendation_id == self.projection.recommendation.recommendation_id:
            return self.projection
        return None


def _projection() -> ReasoningInputProjection:
    context = build_context_snapshot(
        EngineeringContextInputProjection(
            project_id="project-1",
            project_name="Board",
            stage=ContextStage.FIRMWARE_DEVELOPMENT,
            decision_topic="interface",
            constraints=(),
        )
    )
    evidence = build_evidence(
        evidence_id="evidence-1",
        source_type=EvidenceSourceType.LOCAL_KNOWLEDGE,
        trust_basis=EvidenceTrustBasis.VERIFIED,
        summary="Verified interface guidance",
        reference_id="ref-1",
        confidence=1.0,
        source_rank=0,
    )
    recommendation = build_recommendation(context, fuse_evidence((evidence,)))
    return ReasoningInputProjection(
        context_snapshot=context,
        recommendation=recommendation,
        evidence_references=(
            ReasoningEvidenceReference(
                reference_id="evidence-1",
                source_type=EvidenceSourceType.LOCAL_KNOWLEDGE,
            ),
        ),
    )


def test_reasoning_query_returns_safe_wire_shape() -> None:
    projection = _projection()
    app = create_app(
        settings=Settings(_env_file=None),
        service=None,
        workspace_service=None,
        reasoning_layer_port=FakeReasoningPort(),
        reasoning_input_resolver=_Resolver(projection),
    )

    async def exercise() -> httpx.Response:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.post(
                    "/api/reasoning/query",
                    json={
                        "recommendation_id": projection.recommendation.recommendation_id,
                        "mode": "EXPLAIN",
                        "question": "Explain the recommendation.",
                    },
                )

    response = asyncio.run(exercise())
    assert response.status_code == 200
    assert set(response.json()) == {
        "summary",
        "explanation",
        "tradeoffs",
        "risks",
        "references",
        "confidence",
    }
    assert "fingerprint" not in response.text
    assert "provider" not in response.text.casefold()


def test_reasoning_query_fails_closed_when_dependencies_are_missing() -> None:
    app = create_app(
        settings=Settings(_env_file=None), service=None, workspace_service=None
    )

    async def exercise() -> httpx.Response:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.post(
                    "/api/reasoning/query",
                    json={
                        "recommendation_id": "recommendation-1",
                        "mode": "EXPLAIN",
                        "question": "Explain.",
                    },
                )

    response = asyncio.run(exercise())
    assert response.status_code == 503
    assert response.json() == {"error": "REASONING_UNAVAILABLE"}
