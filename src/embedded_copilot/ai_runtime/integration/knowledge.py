"""Adapter for the existing public Knowledge Intelligence Port."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.ai_runtime.models import (
    KnowledgeEvidenceProjection,
    knowledge_evidence_fingerprint,
)
from embedded_copilot.knowledge.intelligence import (
    EngineeringKnowledgeRequest,
    KnowledgeIntelligencePort,
    KnowledgeIntelligenceResult,
)


class KnowledgeIntelligenceAdapter:
    __slots__ = ("_port",)

    def __init__(self, port: KnowledgeIntelligencePort) -> None:
        if not isinstance(port, KnowledgeIntelligencePort):
            raise TypeError("knowledge intelligence port is invalid")
        self._port = port

    def retrieve(
        self,
        *,
        request_id: str,
        query_summary: str,
    ) -> tuple[KnowledgeEvidenceProjection, ...]:
        candidate = self._port.retrieve(
            EngineeringKnowledgeRequest(
                request_id=request_id,
                query_summary=query_summary,
            )
        )
        if type(candidate) is not KnowledgeIntelligenceResult:
            raise ValueError("knowledge result is invalid")
        try:
            result = KnowledgeIntelligenceResult.model_validate(
                candidate.model_copy(deep=True)
            )
        except (TypeError, ValueError, ValidationError):
            raise ValueError("knowledge result is invalid") from None
        projections = tuple(_project(item) for item in result.verified_evidence)
        return tuple(sorted(projections, key=lambda item: item.evidence_id))


def _project(evidence) -> KnowledgeEvidenceProjection:
    references = tuple(
        sorted({item.reference for item in evidence.provenance})
    )
    values = dict(
        evidence_id=evidence.evidence_id,
        summary=evidence.summary,
        source_references=references,
        confidence=evidence.confidence,
    )
    return KnowledgeEvidenceProjection(
        **values,
        fingerprint=knowledge_evidence_fingerprint(**values),
    )

