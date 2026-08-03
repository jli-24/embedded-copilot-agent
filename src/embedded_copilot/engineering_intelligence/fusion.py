from __future__ import annotations

import copy
import hashlib
import json

from .contracts import (
    EngineeringEvidence,
    EngineeringKnowledgeContext,
    EvidenceConflict,
    EvidenceSourceStatus,
    canonical_fingerprint,
)
from .evidence import validate_evidence
from .ranking import evidence_cap, ranking_key


def _conflict_id(
    subject: str,
    parameter: str,
    unit: str,
    evidence_ids: tuple[str, ...],
    values: tuple[str, ...],
) -> str:
    material = json.dumps(
        {
            "evidence_ids": evidence_ids,
            "parameter": parameter,
            "subject": subject,
            "unit": unit,
            "values": values,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "conflict-" + hashlib.sha256(material).hexdigest()[:24]


def fuse_evidence(
    values: tuple[EngineeringEvidence, ...],
    *,
    source_statuses: tuple[EvidenceSourceStatus, ...] = (),
) -> EngineeringKnowledgeContext:
    if not isinstance(values, tuple) or not isinstance(source_statuses, tuple):
        raise ValueError("evidence and source statuses must be tuples")
    checked = tuple(validate_evidence(item) for item in copy.deepcopy(values))
    if len({item.evidence_id for item in checked}) != len(checked):
        raise ValueError("evidence IDs must be unique")
    ranked = tuple(sorted(checked, key=ranking_key))
    grouped: dict[tuple[str, str, str], list[EngineeringEvidence]] = {}
    for item in ranked:
        if item.claim is None:
            continue
        key = (
            item.claim.subject.casefold(),
            item.claim.parameter.casefold(),
            item.claim.unit.casefold(),
        )
        grouped.setdefault(key, []).append(item)
    conflicts: list[EvidenceConflict] = []
    for key, group in sorted(grouped.items()):
        distinct = tuple(sorted({item.claim.value for item in group if item.claim}))
        if len(distinct) < 2:
            continue
        subject, parameter, unit = key
        evidence_ids = tuple(item.evidence_id for item in group)
        conflicts.append(
            EvidenceConflict(
                conflict_id=_conflict_id(
                    subject, parameter, unit, evidence_ids, distinct
                ),
                subject=subject,
                parameter=parameter,
                unit=unit,
                evidence_ids=evidence_ids,
                values=distinct,
            )
        )
    confidence = 0.0
    if ranked:
        confidence = min(ranked[0].confidence, evidence_cap(ranked[0]))
        if conflicts:
            confidence = min(confidence, 0.5)
    statuses = tuple(copy.deepcopy(source_statuses))
    material = EngineeringKnowledgeContext.model_construct(
        evidence=ranked,
        evidence_refs=tuple(item.evidence_id for item in ranked),
        confidence=confidence,
        conflicts=tuple(conflicts),
        source_statuses=statuses,
        fingerprint="sha256:" + "0" * 64,
    )
    return EngineeringKnowledgeContext.model_validate(
        {
            **material.model_dump(mode="python"),
            "fingerprint": canonical_fingerprint(material, exclude={"fingerprint"}),
        }
    )
