from __future__ import annotations

import copy

from embedded_copilot.knowledge.intelligence.models import (
    KnowledgeProvenance,
    KnowledgeSourceCandidate,
    KnowledgeVerificationMethod,
    KnowledgeVerificationOutcome,
    SourceTrustCatalog,
    SourceTrustLevel,
    VerifiedKnowledgeEvidence,
)


class DeterministicKnowledgeVerifier:
    __slots__ = ("_trust_catalog",)

    def __init__(self, trust_catalog: SourceTrustCatalog) -> None:
        self._trust_catalog = SourceTrustCatalog.model_validate(
            copy.deepcopy(trust_catalog)
        )

    def verify(
        self,
        candidates: tuple[KnowledgeSourceCandidate, ...],
    ) -> KnowledgeVerificationOutcome:
        if type(candidates) is not tuple:
            raise TypeError("knowledge candidates must be a tuple")
        checked = tuple(
            KnowledgeSourceCandidate.model_validate(copy.deepcopy(candidate))
            for candidate in candidates
        )
        grouped: dict[str, list[KnowledgeSourceCandidate]] = {}
        for candidate in checked:
            grouped.setdefault(candidate.fact_key, []).append(candidate)

        verified: list[VerifiedKnowledgeEvidence] = []
        rejected_count = 0
        review_required_count = 0
        for fact_key in sorted(grouped):
            group = sorted(
                grouped[fact_key],
                key=lambda item: (
                    item.canonical_value,
                    item.publisher.casefold(),
                    item.evidence_id,
                ),
            )
            values = {item.canonical_value for item in group}
            entity_types = {item.entity_type for item in group}
            failure_rules = {
                (
                    None
                    if item.failure_rule is None
                    else item.failure_rule.model_dump_json()
                )
                for item in group
            }
            if (
                len(values) != 1
                or len(entity_types) != 1
                or len(failure_rules) != 1
            ):
                review_required_count += len(group)
                continue

            trusted: list[tuple[KnowledgeSourceCandidate, SourceTrustLevel]] = []
            for candidate in group:
                trust = self._trust_catalog.trust_for(
                    candidate.source_type,
                    candidate.publisher,
                )
                if trust is None:
                    rejected_count += 1
                else:
                    trusted.append((candidate, trust))
            if not trusted:
                continue

            authoritative = [
                item
                for item, trust in trusted
                if trust is SourceTrustLevel.AUTHORITATIVE
            ]
            if authoritative:
                selected = self._unique_publishers(authoritative)
                method = KnowledgeVerificationMethod.AUTHORITATIVE_SOURCE
            else:
                community = self._unique_publishers(item for item, _ in trusted)
                if len(community) < 2:
                    review_required_count += len(trusted)
                    continue
                selected = community
                method = KnowledgeVerificationMethod.PUBLISHER_CONSENSUS

            representative = selected[0]
            provenance = tuple(
                KnowledgeProvenance(
                    source_type=item.source_type,
                    publisher=item.publisher,
                    reference=item.reference,
                    verification_method=method,
                    verified_at=item.observed_at,
                    confidence=1.0,
                )
                for item in selected
            )
            relationships = tuple(
                sorted(
                    {
                        (relation.relationship_type, relation.target_entity_id): relation
                        for item in selected
                        for relation in item.relationships
                    }.values(),
                    key=lambda relation: (
                        relation.relationship_type.value,
                        relation.target_entity_id,
                    ),
                )
            )
            verified.append(
                VerifiedKnowledgeEvidence(
                    evidence_id=representative.evidence_id,
                    entity_type=representative.entity_type,
                    fact_key=representative.fact_key,
                    canonical_value=representative.canonical_value,
                    summary=representative.summary,
                    provenance=provenance,
                    relationships=relationships,
                    failure_rule=representative.failure_rule,
                )
            )

        return KnowledgeVerificationOutcome(
            verified_evidence=tuple(
                sorted(verified, key=lambda item: (item.fact_key, item.evidence_id))
            ),
            rejected_count=rejected_count,
            review_required_count=review_required_count,
        )

    @staticmethod
    def _unique_publishers(
        candidates,
    ) -> tuple[KnowledgeSourceCandidate, ...]:
        unique: dict[str, KnowledgeSourceCandidate] = {}
        for candidate in candidates:
            key = candidate.publisher.casefold()
            unique.setdefault(key, candidate)
        return tuple(
            sorted(
                unique.values(),
                key=lambda item: (
                    item.source_type.value,
                    item.publisher.casefold(),
                    item.evidence_id,
                ),
            )
        )
