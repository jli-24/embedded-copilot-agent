from __future__ import annotations

import pytest

from embedded_copilot.engineering_context import (
    ApprovedMemoryProjection,
    DatasheetMetadataProjection,
    EngineeringContextQuery,
    EngineeringContextService,
    VerifiedKnowledgeProjection,
)
from embedded_copilot.engineering_context.policy import ContextCategory
from embedded_copilot.engineering_knowledge import (
    EngineeringGraphSnapshot,
    EngineeringKnowledgeNode,
    NodeType,
)


def _memory(memory_id: str = "m1") -> ApprovedMemoryProjection:
    return ApprovedMemoryProjection.create(
        memory_id=memory_id,
        project_id="project-1",
        memory_type="DECISION",
        summary="ESP32-S3 selected",
        decision="selected",
        reason="camera platform evidence",
        source_reference=f"decision:{memory_id}",
        confidence=0.9,
    )


def _graph() -> EngineeringGraphSnapshot:
    node = EngineeringKnowledgeNode.create(
        node_id="memory-m1",
        project_id="project-1",
        node_type=NodeType.DECISION,
        entity_name="ESP32-S3",
        summary="ESP32-S3 selected",
        source_memory_id="m1",
        source_reference="decision:m1",
        confidence=0.9,
        verification_status="APPROVED",
    )
    return EngineeringGraphSnapshot.create(
        project_id="project-1", nodes=(node,), relations=()
    )


class _MemoryPort:
    def __init__(self, values):
        self.values = tuple(values)
        self.calls = 0

    def list_approved(self, project_id: str):
        self.calls += 1
        return tuple(value.model_copy(deep=True) for value in self.values)


class _GraphPort:
    def __init__(self, value):
        self.value = value

    def project(self, project_id: str):
        return self.value.model_copy(deep=True)


class _KnowledgePort:
    def get_snapshot(self, project_id: str):
        return (
            VerifiedKnowledgeProjection.create(
                source_id="knowledge-1",
                project_id="project-1",
                entity_name="camera",
                summary="camera support metadata",
                category=ContextCategory.COMPONENT,
                source_reference="datasheet:camera",
                confidence=0.7,
                verification_status="VERIFIED",
                source_fingerprint="sha256:" + "b" * 64,
            ),
        )


class _DatasheetPort:
    def list_metadata(self, project_id: str, query: str):
        return (
            DatasheetMetadataProjection.create(
                source_id="ds-1",
                project_id="project-1",
                component="ESP32-S3",
                property="camera interface available",
                source_reference="datasheet:esp32-s3",
                confidence=0.6,
                source_fingerprint="sha256:" + "c" * 64,
            ),
        )


def test_fusion_is_read_only_and_preserves_memory_graph_provenance() -> None:
    memory_port = _MemoryPort((_memory(),))
    service = EngineeringContextService(
        memory_port=memory_port,
        graph_port=_GraphPort(_graph()),
        knowledge_port=_KnowledgePort(),
        datasheet_port=_DatasheetPort(),
    )
    snapshot = service.get_context(
        EngineeringContextQuery(project_id="project-1", query="ESP32-S3")
    )
    assert snapshot is not None
    assert snapshot.decisions[0].summary == "ESP32-S3 selected"
    assert {
        source.source_type
        for item in snapshot.decisions
        for source in item.source_references
    } == {"ENGINEERING_MEMORY", "KNOWLEDGE_GRAPH"}
    assert {source.source_type for source in snapshot.sources} >= {
        "ENGINEERING_MEMORY",
        "KNOWLEDGE_GRAPH",
        "DATASHEET_METADATA",
    }
    assert memory_port.calls == 1


def test_same_inputs_are_deterministic_over_repeated_calls() -> None:
    service = EngineeringContextService(
        memory_port=_MemoryPort((_memory(),)), graph_port=_GraphPort(_graph())
    )
    fingerprints = {
        service.get_context(
            EngineeringContextQuery(project_id="project-1", query="ESP32-S3")
        ).fingerprint
        for _ in range(100)
    }
    assert len(fingerprints) == 1


def test_project_mismatch_fails_closed() -> None:
    from embedded_copilot.engineering_context import EngineeringContextRejected

    service = EngineeringContextService(
        memory_port=_MemoryPort((_memory(),)), graph_port=_GraphPort(_graph())
    )
    with pytest.raises(EngineeringContextRejected):
        service.get_context(
            EngineeringContextQuery(project_id="project-2", query="ESP32-S3")
        )
