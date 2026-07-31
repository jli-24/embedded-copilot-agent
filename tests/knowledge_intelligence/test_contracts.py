from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.knowledge.intelligence import (
    EngineeringKnowledgeRequest,
    KnowledgeEntityType,
    KnowledgeProvenance,
    KnowledgeSourceCandidate,
    KnowledgeSourceType,
    KnowledgeVerificationMethod,
)


NOW = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)


def test_contracts_are_frozen_strict_and_include_safe_provenance() -> None:
    request = EngineeringKnowledgeRequest(
        request_id="knowledge-request-1",
        query_summary="ESP32-S3 camera interface constraints",
    )
    candidate = KnowledgeSourceCandidate(
        evidence_id="evidence-esp32-s3-camera",
        entity_type=KnowledgeEntityType.COMPONENT,
        fact_key="component.esp32-s3.camera",
        canonical_value="supported",
        summary="ESP32-S3 provides a camera interface capability.",
        source_type=KnowledgeSourceType.DATASHEET,
        publisher="Espressif",
        reference="https://www.espressif.com/esp32-s3-datasheet#section-5.2",
        observed_at=NOW,
    )
    provenance = KnowledgeProvenance(
        source_type=KnowledgeSourceType.DATASHEET,
        publisher="Espressif",
        reference="https://www.espressif.com/esp32-s3-datasheet#section-5.2",
        verification_method=KnowledgeVerificationMethod.AUTHORITATIVE_SOURCE,
        verified_at=NOW,
        confidence=1.0,
    )

    assert request.query_summary == "ESP32-S3 camera interface constraints"
    assert candidate.publisher == "Espressif"
    assert provenance.verified_at == NOW
    with pytest.raises(ValidationError):
        request.query_summary = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EngineeringKnowledgeRequest(
            request_id="knowledge-request-1",
            query_summary="safe query",
            provider="ollama",  # type: ignore[call-arg]
        )


def test_provenance_rejects_credentials_paths_and_untrusted_confidence() -> None:
    with pytest.raises(ValidationError):
        KnowledgeProvenance(
            source_type=KnowledgeSourceType.WEB,
            publisher="Community",
            reference="https://user:secret@example.com/reference",
            verification_method=KnowledgeVerificationMethod.PUBLISHER_CONSENSUS,
            verified_at=NOW,
            confidence=1.0,
        )
    with pytest.raises(ValidationError):
        KnowledgeProvenance(
            source_type=KnowledgeSourceType.WEB,
            publisher="Community",
            reference="C:\\private\\source.txt",
            verification_method=KnowledgeVerificationMethod.PUBLISHER_CONSENSUS,
            verified_at=NOW,
            confidence=0.7,
        )
