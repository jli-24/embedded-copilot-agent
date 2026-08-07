from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_context import (
    ApprovedMemoryProjection,
    ContextCategory,
    ContextSourceReference,
    ContextSourceType,
    EngineeringContextItem,
    EngineeringContextQuery,
)


def _source() -> ContextSourceReference:
    return ContextSourceReference.create(
        source_type=ContextSourceType.ENGINEERING_MEMORY,
        source_id="memory-m1",
        source_reference="decision:m1",
        source_fingerprint="sha256:" + "a" * 64,
        verification_status="APPROVED",
        confidence=0.9,
    )


def test_context_contracts_are_frozen_strict_and_provenance_bound() -> None:
    item = EngineeringContextItem.create(
        item_id="memory-m1",
        project_id="project-1",
        category=ContextCategory.DECISION,
        entity_name="ESP32-S3",
        summary="cafe\u0301 decision",
        source_references=(_source(),),
        confidence=0.9,
        verification_status="APPROVED",
    )
    assert item.summary == "café decision"
    with pytest.raises((TypeError, ValidationError)):
        item.summary = "changed"
    with pytest.raises(ValidationError):
        EngineeringContextItem.model_validate({**item.model_dump(), "extra": "x"})
    with pytest.raises(ValidationError):
        EngineeringContextItem.create(
            item_id="item-2",
            project_id="project-1",
            category=ContextCategory.DECISION,
            entity_name="ESP32-S3",
            summary="missing provenance",
            source_references=(),
            confidence=0.9,
            verification_status="APPROVED",
        )


def test_collections_are_tuple_only_and_fingerprints_reject_tampering() -> None:
    source = _source()
    with pytest.raises((TypeError, ValidationError)):
        EngineeringContextItem.create(
            item_id="item-1",
            project_id="project-1",
            category=ContextCategory.COMPONENT,
            entity_name="camera",
            summary="metadata",
            source_references=[source],
            confidence=0.7,
            verification_status="SOURCE_METADATA",
        )
    memory = ApprovedMemoryProjection.create(
        memory_id="m1",
        project_id="project-1",
        memory_type="DECISION",
        summary="ESP32-S3 selected",
        decision="selected",
        reason="evidence",
        source_reference="decision:m1",
        confidence=0.9,
    )
    with pytest.raises(ValidationError):
        ApprovedMemoryProjection.model_validate(
            {**memory.model_dump(), "summary": "tampered"}
        )


def test_query_normalizes_text_before_validation() -> None:
    query = EngineeringContextQuery(project_id="project-1", query="cafe\u0301")
    assert query.query == "café"
