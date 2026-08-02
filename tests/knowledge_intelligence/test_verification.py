from __future__ import annotations

from datetime import datetime

from embedded_copilot.knowledge.intelligence import (
    KnowledgeSourceType,
    KnowledgeVerificationMethod,
    SourceTrustCatalog,
    SourceTrustEntry,
    SourceTrustLevel,
)
from embedded_copilot.knowledge.intelligence.verification.service import (
    DeterministicKnowledgeVerifier,
)

from .conftest import source_candidate


def test_authoritative_single_source_is_verified_with_provenance(
    trust_catalog: SourceTrustCatalog,
    observed_at: datetime,
) -> None:
    candidate = source_candidate(
        evidence_id="official-1",
        publisher="Espressif",
        source_type=KnowledgeSourceType.DATASHEET,
        observed_at=observed_at,
    )

    outcome = DeterministicKnowledgeVerifier(trust_catalog).verify((candidate,))

    assert outcome.rejected_count == 0
    assert outcome.review_required_count == 0
    evidence = outcome.verified_evidence[0]
    assert evidence.confidence == 1.0
    assert evidence.provenance[0].publisher == "Espressif"
    assert (
        evidence.provenance[0].verification_method
        is KnowledgeVerificationMethod.AUTHORITATIVE_SOURCE
    )
    assert evidence.provenance[0].verified_at == observed_at


def test_community_requires_two_independent_publishers_and_ignores_confidence(
    trust_catalog: SourceTrustCatalog,
    observed_at: datetime,
) -> None:
    first = source_candidate(
        evidence_id="community-1",
        publisher="Community A",
        observed_at=observed_at,
    )
    duplicate = first.model_copy(update={"evidence_id": "community-duplicate"})
    second = source_candidate(
        evidence_id="community-2",
        publisher="Community B",
        observed_at=observed_at,
    )
    verifier = DeterministicKnowledgeVerifier(trust_catalog)

    insufficient = verifier.verify((first, duplicate))
    verified = verifier.verify((second, first))

    assert insufficient.verified_evidence == ()
    assert insufficient.review_required_count == 2
    assert tuple(item.publisher for item in verified.verified_evidence[0].provenance) == (
        "Community A",
        "Community B",
    )
    assert all(
        item.confidence == 1.0
        for item in verified.verified_evidence[0].provenance
    )


def test_conflict_requires_review_and_unknown_source_is_rejected(
    trust_catalog: SourceTrustCatalog,
    observed_at: datetime,
) -> None:
    first = source_candidate(
        evidence_id="community-1",
        publisher="Community A",
        observed_at=observed_at,
    )
    conflict = source_candidate(
        evidence_id="community-2",
        publisher="Community B",
        canonical_value="unsupported",
        observed_at=observed_at,
    )
    unknown = source_candidate(
        evidence_id="unknown-1",
        publisher="Unknown Publisher",
        observed_at=observed_at,
    ).model_copy(update={"fact_key": "capability.unknown"})

    outcome = DeterministicKnowledgeVerifier(trust_catalog).verify(
        (unknown, conflict, first)
    )

    assert outcome.verified_evidence == ()
    assert outcome.review_required_count == 2
    assert outcome.rejected_count == 1


def test_same_publisher_across_source_types_is_not_independent(
    observed_at: datetime,
) -> None:
    catalog = SourceTrustCatalog(
        entries=(
            SourceTrustEntry(
                source_type=KnowledgeSourceType.WEB,
                publisher="Same Publisher",
                trust_level=SourceTrustLevel.COMMUNITY,
            ),
            SourceTrustEntry(
                source_type=KnowledgeSourceType.GITHUB,
                publisher="Same Publisher",
                trust_level=SourceTrustLevel.COMMUNITY,
            ),
        )
    )
    web = source_candidate(
        evidence_id="same-web",
        publisher="Same Publisher",
        observed_at=observed_at,
    )
    github = source_candidate(
        evidence_id="same-github",
        publisher="Same Publisher",
        source_type=KnowledgeSourceType.GITHUB,
        observed_at=observed_at,
    )

    outcome = DeterministicKnowledgeVerifier(catalog).verify((web, github))

    assert outcome.verified_evidence == ()
    assert outcome.review_required_count == 2
