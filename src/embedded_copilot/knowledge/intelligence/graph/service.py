from __future__ import annotations

import copy
import hashlib
import json

from embedded_copilot.knowledge.intelligence.exceptions import (
    KnowledgeGraphRejected,
)
from embedded_copilot.knowledge.intelligence.models import (
    FrozenKnowledgeGraphSnapshot,
    KnowledgeGraphEntity,
    KnowledgeGraphEvidenceProjection,
    KnowledgeGraphProjectionRequest,
    KnowledgeGraphQuery,
    KnowledgeGraphRelationship,
    VerifiedKnowledgeEvidence,
)


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class KnowledgeGraphProjector:
    __slots__ = ()

    def project(
        self,
        request: KnowledgeGraphProjectionRequest,
    ) -> FrozenKnowledgeGraphSnapshot:
        try:
            checked = KnowledgeGraphProjectionRequest.model_validate(
                copy.deepcopy(request)
            )
            by_entity: dict[str, list[VerifiedKnowledgeEvidence]] = {}
            for evidence in checked.evidence:
                by_entity.setdefault(evidence.fact_key, []).append(evidence)

            entities: list[KnowledgeGraphEntity] = []
            for entity_id in sorted(by_entity):
                evidence_items = sorted(
                    by_entity[entity_id], key=lambda item: item.evidence_id
                )
                identities = {
                    (
                        item.entity_type,
                        item.canonical_value,
                        item.summary,
                        (
                            None
                            if item.failure_rule is None
                            else item.failure_rule.model_dump_json()
                        ),
                    )
                    for item in evidence_items
                }
                if len(identities) != 1:
                    raise KnowledgeGraphRejected()
                representative = evidence_items[0]
                entities.append(
                    KnowledgeGraphEntity(
                        entity_id=entity_id,
                        entity_type=representative.entity_type,
                        canonical_value=representative.canonical_value,
                        summary=representative.summary,
                        evidence=tuple(evidence_items),
                    )
                )

            known_entities = {entity.entity_id for entity in entities}
            relation_evidence: dict[
                tuple[str, object, str], set[str]
            ] = {}
            for evidence in checked.evidence:
                for relation in evidence.relationships:
                    if relation.target_entity_id not in known_entities:
                        raise KnowledgeGraphRejected()
                    key = (
                        evidence.fact_key,
                        relation.relationship_type,
                        relation.target_entity_id,
                    )
                    relation_evidence.setdefault(key, set()).add(evidence.evidence_id)

            relationships: list[KnowledgeGraphRelationship] = []
            for (source_id, relation_type, target_id), evidence_ids in sorted(
                relation_evidence.items(),
                key=lambda item: (
                    item[0][0],
                    item[0][1].value,
                    item[0][2],
                ),
            ):
                material = f"{source_id}|{relation_type.value}|{target_id}"
                relationship_id = (
                    "relation:" + hashlib.sha256(material.encode("utf-8")).hexdigest()
                )
                relationships.append(
                    KnowledgeGraphRelationship(
                        relationship_id=relationship_id,
                        source_entity_id=source_id,
                        relationship_type=relation_type,
                        target_entity_id=target_id,
                        evidence_ids=tuple(sorted(evidence_ids)),
                    )
                )

            payload: dict[str, object] = {
                "schema_version": "1.0",
                "snapshot_id": checked.snapshot_id,
                "entities": [item.model_dump(mode="json") for item in entities],
                "relationships": [
                    item.model_dump(mode="json") for item in relationships
                ],
            }
            return FrozenKnowledgeGraphSnapshot(
                snapshot_id=checked.snapshot_id,
                entities=tuple(entities),
                relationships=tuple(relationships),
                fingerprint=_fingerprint(payload),
            )
        except KnowledgeGraphRejected:
            raise
        except Exception:
            raise KnowledgeGraphRejected() from None

    def query(
        self,
        request: KnowledgeGraphQuery,
    ) -> KnowledgeGraphEvidenceProjection:
        try:
            checked = KnowledgeGraphQuery.model_validate(copy.deepcopy(request))
            selected_ids = set(checked.entity_ids)
            if selected_ids and not selected_ids.issubset(
                {item.entity_id for item in checked.snapshot.entities}
            ):
                raise KnowledgeGraphRejected()
            entities = tuple(
                item
                for item in checked.snapshot.entities
                if not selected_ids or item.entity_id in selected_ids
            )
            relation_types = set(checked.relationship_types)
            relationships = tuple(
                item
                for item in checked.snapshot.relationships
                if (
                    not relation_types
                    or item.relationship_type in relation_types
                )
                and (
                    not selected_ids
                    or item.source_entity_id in selected_ids
                    or item.target_entity_id in selected_ids
                )
            )
            evidence_by_id = {
                evidence.evidence_id: evidence
                for entity in entities
                for evidence in entity.evidence
            }
            return KnowledgeGraphEvidenceProjection(
                query_id=checked.query_id,
                snapshot_fingerprint=checked.snapshot.fingerprint,
                evidence=tuple(
                    evidence_by_id[key] for key in sorted(evidence_by_id)
                ),
                relationships=relationships,
            )
        except KnowledgeGraphRejected:
            raise
        except Exception:
            raise KnowledgeGraphRejected() from None
