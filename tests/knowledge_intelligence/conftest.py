from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.knowledge.intelligence import (
    KnowledgeEntityType,
    KnowledgeSourceCandidate,
    KnowledgeSourceType,
    SourceTrustCatalog,
    SourceTrustEntry,
    SourceTrustLevel,
)


@pytest.fixture
def observed_at() -> datetime:
    return datetime(2026, 8, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def trust_catalog() -> SourceTrustCatalog:
    return SourceTrustCatalog(
        entries=(
            SourceTrustEntry(
                source_type=KnowledgeSourceType.DATASHEET,
                publisher="Espressif",
                trust_level=SourceTrustLevel.AUTHORITATIVE,
            ),
            SourceTrustEntry(
                source_type=KnowledgeSourceType.WEB,
                publisher="Community A",
                trust_level=SourceTrustLevel.COMMUNITY,
            ),
            SourceTrustEntry(
                source_type=KnowledgeSourceType.WEB,
                publisher="Community B",
                trust_level=SourceTrustLevel.COMMUNITY,
            ),
        )
    )


def source_candidate(
    *,
    evidence_id: str,
    publisher: str,
    observed_at: datetime,
    canonical_value: str = "supported",
    source_type: KnowledgeSourceType = KnowledgeSourceType.WEB,
) -> KnowledgeSourceCandidate:
    return KnowledgeSourceCandidate(
        evidence_id=evidence_id,
        entity_type=KnowledgeEntityType.CAPABILITY,
        fact_key="capability.esp32-s3.camera",
        canonical_value=canonical_value,
        summary="ESP32-S3 camera interface capability.",
        source_type=source_type,
        publisher=publisher,
        reference=f"https://example.com/{evidence_id}",
        observed_at=observed_at,
        provider_confidence=0.01,
    )
