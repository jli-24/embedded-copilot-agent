from __future__ import annotations

import hashlib

from embedded_copilot.datasheet_runtime import DatasheetResponse
from embedded_copilot.knowledge.intelligence.models import (
    DatasheetKnowledgeRequest,
    KnowledgeEntityType,
    KnowledgeSourceCandidate,
)
from embedded_copilot.knowledge.source import KnowledgeSourceType


def _evidence_id(request_id: str, fact_key: str) -> str:
    material = f"{request_id}|{fact_key}".encode("utf-8")
    return f"evidence:{hashlib.sha256(material).hexdigest()}"


class DatasheetCandidateProjector:
    __slots__ = ()

    def project(
        self,
        request: DatasheetKnowledgeRequest,
        response: DatasheetResponse,
    ) -> tuple[KnowledgeSourceCandidate, ...]:
        summary = response.summary
        file_id = summary.file_id
        candidates: list[KnowledgeSourceCandidate] = []
        if summary.component_candidate is not None:
            component = summary.component_candidate
            fact_key = f"component.{file_id}.identity"
            value = (
                component.family
                if component.model is None
                else f"{component.family}:{component.model}"
            )
            candidates.append(
                self._candidate(
                    request,
                    entity_type=KnowledgeEntityType.COMPONENT,
                    fact_key=fact_key,
                    canonical_value=value,
                    summary=f"Component candidate {value}.",
                )
            )
        for interface in summary.interface_candidates:
            fact_key = f"interface.{file_id}.{interface.name.casefold()}"
            candidates.append(
                self._candidate(
                    request,
                    entity_type=KnowledgeEntityType.INTERFACE,
                    fact_key=fact_key,
                    canonical_value=interface.name,
                    summary=f"Interface candidate {interface.name}.",
                )
            )
        for index, electrical in enumerate(summary.electrical_candidates):
            fact_key = f"constraint.{file_id}.{electrical.kind}.{index}"
            value = (
                f"minimum={electrical.minimum};maximum={electrical.maximum};"
                f"unit={electrical.unit}"
            )
            candidates.append(
                self._candidate(
                    request,
                    entity_type=KnowledgeEntityType.CONSTRAINT,
                    fact_key=fact_key,
                    canonical_value=value,
                    summary=f"Electrical constraint candidate {electrical.kind}.",
                )
            )
        for section in summary.section_candidates:
            section_key = section.name.casefold().replace(" ", "-")
            fact_key = f"reference.{file_id}.{section_key}"
            candidates.append(
                self._candidate(
                    request,
                    entity_type=KnowledgeEntityType.REFERENCE_DESIGN,
                    fact_key=fact_key,
                    canonical_value=section.name,
                    summary=f"Datasheet section candidate {section.name}.",
                )
            )
        return tuple(sorted(candidates, key=lambda item: item.fact_key))

    @staticmethod
    def _candidate(
        request: DatasheetKnowledgeRequest,
        *,
        entity_type: KnowledgeEntityType,
        fact_key: str,
        canonical_value: str,
        summary: str,
    ) -> KnowledgeSourceCandidate:
        return KnowledgeSourceCandidate(
            evidence_id=_evidence_id(request.request_id, fact_key),
            entity_type=entity_type,
            fact_key=fact_key,
            canonical_value=canonical_value,
            summary=summary,
            source_type=KnowledgeSourceType.DATASHEET,
            publisher=request.publisher,
            reference=request.reference,
            observed_at=request.observed_at,
        )
