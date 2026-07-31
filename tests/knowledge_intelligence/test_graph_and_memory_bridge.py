from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.knowledge.intelligence import (
    FailureRuleCandidate,
    KnowledgeEntityType,
    KnowledgeFailureSeverity,
    KnowledgeGraphProjectionRequest,
    KnowledgeGraphQuery,
    KnowledgeMemoryBridgeRejected,
    KnowledgeRelationshipCandidate,
    KnowledgeRelationshipType,
    KnowledgeSourceType,
    MemoryBridgeRequest,
    SourceTrustCatalog,
    VerifiedKnowledgeEvidence,
)
from embedded_copilot.knowledge.intelligence.graph.service import (
    KnowledgeGraphProjector,
)
from embedded_copilot.knowledge.intelligence.memory_bridge.service import (
    KnowledgeMemoryBridge,
)
from embedded_copilot.knowledge.intelligence.verification.service import (
    DeterministicKnowledgeVerifier,
)

from .conftest import source_candidate


def _verified(
    trust_catalog: SourceTrustCatalog,
    observed_at: datetime,
) -> VerifiedKnowledgeEvidence:
    candidate = source_candidate(
        evidence_id="component-evidence",
        publisher="Espressif",
        source_type=KnowledgeSourceType.DATASHEET,
        observed_at=observed_at,
    )
    return DeterministicKnowledgeVerifier(trust_catalog).verify(
        (candidate,)
    ).verified_evidence[0]


def test_graph_snapshot_is_stable_and_query_returns_evidence_only(
    trust_catalog: SourceTrustCatalog,
    observed_at: datetime,
) -> None:
    component = _verified(trust_catalog, observed_at)
    interface = component.model_copy(
        update={
            "evidence_id": "interface-evidence",
            "entity_type": KnowledgeEntityType.INTERFACE,
            "fact_key": "interface.esp32-s3.camera",
            "canonical_value": "camera",
            "summary": "ESP32-S3 camera interface.",
            "relationships": (
                KnowledgeRelationshipCandidate(
                    relationship_type=KnowledgeRelationshipType.REQUIRES,
                    target_entity_id=component.fact_key,
                ),
            ),
        }
    )
    projector = KnowledgeGraphProjector()
    first = projector.project(
        KnowledgeGraphProjectionRequest(
            snapshot_id="knowledge-snapshot-1",
            evidence=(interface, component),
        )
    )
    second = projector.project(
        KnowledgeGraphProjectionRequest(
            snapshot_id="knowledge-snapshot-1",
            evidence=(component, interface),
        )
    )

    assert first == second
    assert first.fingerprint.startswith("sha256:")
    projection = projector.query(
        KnowledgeGraphQuery(
            query_id="graph-query-1",
            snapshot=first,
            entity_ids=(interface.fact_key,),
        )
    )
    assert tuple(item.evidence_id for item in projection.evidence) == (
        "interface-evidence",
    )
    assert projection.relationships[0].relationship_type is (
        KnowledgeRelationshipType.REQUIRES
    )
    assert not hasattr(projection, "plan")
    assert not hasattr(projection, "agent_name")

    tampered = first.model_dump(mode="python")
    tampered["entities"][0]["summary"] = "tampered"
    with pytest.raises(ValidationError):
        type(first).model_validate(tampered)


def test_memory_bridge_projects_verified_failure_rule_without_mutation(
    trust_catalog: SourceTrustCatalog,
    observed_at: datetime,
) -> None:
    base = _verified(trust_catalog, observed_at)
    failure = base.model_copy(
        update={
            "evidence_id": "failure-rule-1",
            "entity_type": KnowledgeEntityType.FAILURE_RULE,
            "fact_key": "failure.esp32.camera.power",
            "canonical_value": "camera-requires-stable-power",
            "summary": "Camera initialization requires stable power.",
            "failure_rule": FailureRuleCandidate(
                issue_key="camera-power",
                title="Camera power instability",
                severity=KnowledgeFailureSeverity.HIGH,
                description_summary="Camera initialization can fail on unstable power.",
                mitigation_summary="Validate supply stability before initialization.",
            ),
        }
    )
    before = failure.model_dump(mode="json")
    request = MemoryBridgeRequest(
        request_id="memory-request-1",
        operation_id="memory-operation-1",
        project_id="project-1",
        memory_id="memory-1",
        record_id="record-1",
        expected_revision=0,
        caller="knowledge-reviewer",
        requested_at=observed_at,
        evidence=failure,
    )

    projection = KnowledgeMemoryBridge().project(request)

    assert projection.candidate.issue_key == "camera-power"
    assert projection.create_request.payload == projection.candidate
    assert projection.create_request.provenance.source_type.value == (
        "VERIFICATION_RESULT"
    )
    assert failure.model_dump(mode="json") == before
    assert not hasattr(projection, "memory_port")
    with pytest.raises(KnowledgeMemoryBridgeRejected):
        KnowledgeMemoryBridge().project(request.model_copy(update={"evidence": base}))
