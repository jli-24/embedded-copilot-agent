from __future__ import annotations

import copy
import hashlib
import json
from typing import Protocol

from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.memory_automation import MemoryCandidate, MemoryReviewStatus

from embedded_copilot.datasheet_agent import project_datasheet_evidence
from embedded_copilot.web_research_agent import (
    UnavailableWebResearchPort,
    WebEvidenceProjection,
    WebResearchPort,
    WebResearchRequest,
    WebResearchUnavailable,
)

from .context import validate_context_snapshot
from .contracts import (
    EvidenceAvailability,
    EvidenceSourceStatus,
    EvidenceSourceType,
    EvidenceTrustBasis,
    EngineeringEvidence,
    EngineeringIntelligenceRequest,
    EngineeringIntelligenceResponse,
    MemoryReferenceProjection,
)
from .evidence import build_evidence
from .fusion import fuse_evidence
from .recommendation import build_recommendation


class KnowledgeReadPort(Protocol):
    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...


class MemoryEvidencePort(Protocol):
    def resolve(
        self, references: tuple[MemoryReferenceProjection, ...]
    ) -> tuple[MemoryCandidate, ...]: ...


class EngineeringIntelligencePort(Protocol):
    async def query(
        self, request: EngineeringIntelligenceRequest
    ) -> EngineeringIntelligenceResponse: ...


class EngineeringIntelligenceService:
    def __init__(
        self,
        *,
        knowledge_port: KnowledgeReadPort | None = None,
        memory_port: MemoryEvidencePort | None = None,
        datasheet_port: object | None = None,
        web_port: WebResearchPort | None = None,
    ) -> None:
        self._knowledge_port = knowledge_port
        self._memory_port = memory_port
        self._datasheet_port = datasheet_port
        self._web_port = web_port or UnavailableWebResearchPort()

    async def query(
        self, request: EngineeringIntelligenceRequest
    ) -> EngineeringIntelligenceResponse:
        if type(request) is not EngineeringIntelligenceRequest:
            raise TypeError("intelligence request must be a typed projection")
        checked = EngineeringIntelligenceRequest.model_validate(copy.deepcopy(request))
        snapshot = validate_context_snapshot(checked.context_snapshot)
        values: list[EngineeringEvidence] = []
        statuses: list[EvidenceSourceStatus] = []

        local_status = EvidenceAvailability.NOT_CONFIGURED
        if self._knowledge_port is not None:
            try:
                query = KnowledgeQuery(
                    query=checked.question,
                    sources=[KnowledgeSource.LOCAL],
                    top_k=32,
                    metadata={},
                )
                results = self._knowledge_port.search(query)
                if not isinstance(results, list):
                    raise ValueError("knowledge result is invalid")
                for rank, result in enumerate(copy.deepcopy(results)):
                    if (
                        type(result) is not KnowledgeResult
                        or result.source is not KnowledgeSource.LOCAL
                    ):
                        raise ValueError("knowledge result is invalid")
                    values.append(
                        build_evidence(
                            evidence_id=f"local-{result.id}",
                            source_type=EvidenceSourceType.LOCAL_KNOWLEDGE,
                            trust_basis=EvidenceTrustBasis.PROJECTED,
                            summary=result.title,
                            reference_id=result.id,
                            confidence=0.5,
                            source_rank=rank,
                        )
                    )
                local_status = EvidenceAvailability.AVAILABLE
            except Exception:
                local_status = EvidenceAvailability.INVALID
        statuses.append(
            EvidenceSourceStatus(
                source_type=EvidenceSourceType.LOCAL_KNOWLEDGE, status=local_status
            )
        )

        memory_status = EvidenceAvailability.NOT_CONFIGURED
        if snapshot.memory_references:
            if self._memory_port is None:
                memory_status = EvidenceAvailability.UNAVAILABLE
            else:
                try:
                    candidates = self._memory_port.resolve(
                        copy.deepcopy(snapshot.memory_references)
                    )
                    if not isinstance(candidates, tuple):
                        raise ValueError("memory result is invalid")
                    expected = {
                        item.reference_id: item.memory_id
                        for item in snapshot.memory_references
                    }
                    for rank, candidate in enumerate(copy.deepcopy(candidates)):
                        if type(candidate) is not MemoryCandidate:
                            raise ValueError("memory result is invalid")
                        if candidate.review_status is not MemoryReviewStatus.APPROVED:
                            raise ValueError("memory candidate is not approved")
                        if (
                            expected.get(candidate.source.source_reference)
                            != candidate.memory_id
                        ):
                            raise ValueError("memory reference mismatch")
                        values.append(
                            build_evidence(
                                evidence_id=f"memory-{candidate.memory_id}",
                                source_type=EvidenceSourceType.MEMORY,
                                trust_basis=EvidenceTrustBasis.HUMAN_APPROVED,
                                summary=candidate.summary,
                                reference_id=candidate.source.source_reference,
                                confidence=candidate.confidence,
                                source_rank=rank,
                            )
                        )
                    memory_status = EvidenceAvailability.AVAILABLE
                except Exception:
                    memory_status = EvidenceAvailability.INVALID
        statuses.append(
            EvidenceSourceStatus(
                source_type=EvidenceSourceType.MEMORY, status=memory_status
            )
        )

        datasheet_status = EvidenceAvailability.NOT_CONFIGURED
        if snapshot.datasheet_references:
            if self._datasheet_port is None:
                datasheet_status = EvidenceAvailability.UNAVAILABLE
            else:
                successful = 0
                for reference in snapshot.datasheet_references:
                    try:
                        projected = await project_datasheet_evidence(
                            self._datasheet_port,
                            session_id=reference.session_id,
                            file_id=reference.file_id,
                            reference_id=reference.reference_id,
                        )
                        values.extend(projected)
                        successful += 1
                    except Exception:
                        continue
                datasheet_status = (
                    EvidenceAvailability.AVAILABLE
                    if successful == len(snapshot.datasheet_references)
                    else (
                        EvidenceAvailability.PARTIAL
                        if successful
                        else EvidenceAvailability.INVALID
                    )
                )
        statuses.append(
            EvidenceSourceStatus(
                source_type=EvidenceSourceType.DATASHEET, status=datasheet_status
            )
        )

        web_status = EvidenceAvailability.NOT_CONFIGURED
        try:
            web_values = await self._web_port.research(
                WebResearchRequest(query=checked.question)
            )
            if not isinstance(web_values, tuple):
                raise ValueError("web result is invalid")
            for rank, item in enumerate(copy.deepcopy(web_values)):
                if type(item) is not WebEvidenceProjection:
                    raise ValueError("web result is invalid")
                values.append(
                    build_evidence(
                        evidence_id=f"web-{item.reference}",
                        source_type=EvidenceSourceType.WEB,
                        trust_basis=EvidenceTrustBasis.PROJECTED,
                        summary=item.summary,
                        reference_id=item.reference,
                        confidence=item.confidence,
                        source_rank=rank,
                    )
                )
            web_status = EvidenceAvailability.AVAILABLE
        except WebResearchUnavailable:
            web_status = EvidenceAvailability.NOT_CONFIGURED
        except Exception:
            web_status = EvidenceAvailability.INVALID
        statuses.append(
            EvidenceSourceStatus(source_type=EvidenceSourceType.WEB, status=web_status)
        )

        fused = fuse_evidence(tuple(values), source_statuses=tuple(statuses))
        recommendation = build_recommendation(snapshot, fused)
        query_material = json.dumps(
            {
                "project_id": checked.project_id,
                "question": checked.question,
                "context_fingerprint": snapshot.context_fingerprint,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        query_fingerprint = "sha256:" + hashlib.sha256(query_material).hexdigest()
        return EngineeringIntelligenceResponse(
            recommendation=recommendation,
            knowledge_context=fused,
            query_fingerprint=query_fingerprint,
        )
