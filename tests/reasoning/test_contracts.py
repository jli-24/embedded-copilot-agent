from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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
    ReasoningMode,
    ReasoningRequest,
    ReasoningResponse,
)


def _snapshot():
    return build_context_snapshot(
        EngineeringContextInputProjection(
            project_id="project-1",
            project_name="Board",
            stage=ContextStage.FIRMWARE_DEVELOPMENT,
            decision_topic="interface",
            constraints=("review timing",),
        )
    )


def _recommendation():
    evidence = build_evidence(
        evidence_id="evidence-1",
        source_type=EvidenceSourceType.LOCAL_KNOWLEDGE,
        trust_basis=EvidenceTrustBasis.VERIFIED,
        summary="Verified interface guidance",
        reference_id="ref-1",
        confidence=1.0,
        source_rank=0,
    )
    return build_recommendation(_snapshot(), fuse_evidence((evidence,)))


def _request() -> ReasoningRequest:
    snapshot = _snapshot()
    recommendation = _recommendation()
    reference = ReasoningEvidenceReference(
        reference_id="evidence-1", source_type=EvidenceSourceType.LOCAL_KNOWLEDGE
    )
    return ReasoningRequest(
        request_id="request-1",
        project_id="project-1",
        recommendation_id=recommendation.recommendation_id,
        context_fingerprint=snapshot.context_fingerprint,
        evidence_references=(reference,),
        question="Explain this recommendation.",
        reasoning_mode=ReasoningMode.EXPLAIN,
        context_snapshot=snapshot,
        recommendation=recommendation,
    )


def test_contracts_are_frozen_strict_and_fingerprinted() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        request.question = "changed"
    with pytest.raises(ValidationError):
        ReasoningRequest.model_validate(
            {**request.model_dump(mode="python"), "unexpected": True}
        )
    material = ReasoningResponse.model_construct(
        summary="A reviewable explanation.",
        explanation="The recommendation follows the verified context.",
        tradeoffs=("More review effort",),
        risks=("Timing assumptions need validation",),
        references=("ref-1",),
        confidence=0.75,
        fingerprint="sha256:" + "0" * 64,
    )
    from embedded_copilot.reasoning.models import canonical_fingerprint

    response = ReasoningResponse.model_validate(
        {
            **material.model_dump(mode="python"),
            "fingerprint": canonical_fingerprint(material, exclude={"fingerprint"}),
        }
    )
    assert response.fingerprint.startswith("sha256:")
    with pytest.raises(ValidationError):
        ReasoningResponse.model_validate(
            {**response.model_dump(mode="python"), "fingerprint": "sha256:" + "f" * 64}
        )


def test_request_rejects_lists_naive_datetime_and_sensitive_text() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        ReasoningRequest.model_validate(
            {**request.model_dump(mode="python"), "evidence_references": []}
        )
    with pytest.raises(ValidationError):
        ReasoningRequest.model_validate(
            {**request.model_dump(mode="python"), "question": "api_key=SECRET"}
        )
    assert datetime(2026, 1, 1, tzinfo=UTC).astimezone(UTC).tzinfo is UTC


def test_response_serialization_is_deterministic() -> None:
    material = ReasoningResponse.model_construct(
        summary="Summary",
        explanation="Explanation",
        tradeoffs=(),
        risks=(),
        references=(),
        confidence=0.5,
        fingerprint="sha256:" + "0" * 64,
    )
    from embedded_copilot.reasoning.models import canonical_fingerprint

    response = ReasoningResponse.model_validate(
        {
            **material.model_dump(mode="python"),
            "fingerprint": canonical_fingerprint(material, exclude={"fingerprint"}),
        }
    )
    assert response.model_dump(mode="json") == response.model_dump(mode="json")
    assert "chain_of_thought" not in response.model_dump()
