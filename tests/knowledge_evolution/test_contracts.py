from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.knowledge_evolution.adapters.fake import (
    FakeKnowledgeEvolutionPort,
    FakeKnowledgeRetrievalPort,
)
from embedded_copilot.knowledge_evolution.contracts import (
    EngineeringKnowledgeRelation,
    KnowledgeConfidence,
    KnowledgeQueryRequest,
    validate_snapshot,
)


def test_fake_snapshot_and_retrieval_are_deterministic() -> None:
    snapshots = [FakeKnowledgeEvolutionPort().get_snapshot("demo") for _ in range(100)]
    assert len({item.fingerprint for item in snapshots}) == 1
    request = KnowledgeQueryRequest(
        project_id="demo",
        requirement_reference="requirement:demo",
        context_fingerprint=snapshots[0].fingerprint,
    )
    suggestions = [FakeKnowledgeRetrievalPort().query(request) for _ in range(100)]
    assert len({item[0].fingerprint for item in suggestions}) == 1


def test_snapshot_is_frozen_and_relation_identity_is_checked() -> None:
    snapshot = FakeKnowledgeEvolutionPort().get_snapshot("demo")
    with pytest.raises((ValidationError, TypeError)):
        snapshot.project_id = "other"  # type: ignore[misc]
    with pytest.raises((ValidationError, TypeError)):
        validate_snapshot({**snapshot.model_dump(mode="python"), "nodes": list(snapshot.nodes)})
    with pytest.raises(ValidationError):
        EngineeringKnowledgeRelation.create(
            relation_id="relation:bad",
            source_id="node:missing",
            target_id="node:missing2",
            relation_type="USED_WITH",
            evidence_reference="verified:unverified",
            confidence=KnowledgeConfidence.UNVERIFIED,
        )
