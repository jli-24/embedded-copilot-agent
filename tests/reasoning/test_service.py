from __future__ import annotations

import copy

import pytest

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
    ReasoningMode,
    ReasoningRequestRejected,
    ReasoningService,
    ReasoningRuntimeUnavailable,
)
from embedded_copilot.reasoning.adapters.fake import FakeReasoningPort
from embedded_copilot.reasoning.adapters.local_model import LocalModelReasoningAdapter


def _input() -> ReasoningInputProjection:
    context = build_context_snapshot(
        EngineeringContextInputProjection(
            project_id="project-1",
            project_name="Board",
            stage=ContextStage.FIRMWARE_DEVELOPMENT,
            decision_topic="interface",
            constraints=("review timing",),
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


def test_fake_reasoning_is_deterministic_and_input_is_not_mutated() -> None:
    projection = _input()
    before = projection.model_dump(mode="json")
    service = ReasoningService(FakeReasoningPort())
    responses = tuple(
        service.reason(
            projection=projection,
            question="Explain the recommendation.",
            reasoning_mode=ReasoningMode.EXPLAIN,
            request_id="request-1",
        )
        for _ in range(100)
    )
    assert len({response.fingerprint for response in responses}) == 1
    assert projection.model_dump(mode="json") == before
    assert responses[0].confidence < 1.0


def test_service_rejects_binding_mismatch_and_unavailable_adapter() -> None:
    projection = _input()
    with pytest.raises(ReasoningRequestRejected):
        ReasoningService(FakeReasoningPort()).reason(
            projection=projection,
            question="Explain.",
            reasoning_mode=ReasoningMode.EXPLAIN,
            request_id="request-1",
            recommendation_id="other-recommendation",
        )
    with pytest.raises(ReasoningRuntimeUnavailable):
        ReasoningService(LocalModelReasoningAdapter()).reason(
            projection=projection,
            question="Explain.",
            reasoning_mode=ReasoningMode.EXPLAIN,
            request_id="request-1",
        )


def test_fake_adapter_does_not_expose_sensitive_fields() -> None:
    projection = _input()
    response = ReasoningService(FakeReasoningPort()).reason(
        projection=copy.deepcopy(projection),
        question="Compare the available options.",
        reasoning_mode=ReasoningMode.COMPARE,
        request_id="request-1",
    )
    dumped = response.model_dump(mode="json")
    assert set(dumped) == {
        "summary",
        "explanation",
        "tradeoffs",
        "risks",
        "references",
        "confidence",
        "fingerprint",
    }
    assert "prompt" not in response.model_dump()
    assert "provider_details" not in response.model_dump()
