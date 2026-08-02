from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.knowledge.intelligence.models import (
    DatasheetKnowledgeRequest,
    EngineeringKnowledgeRequest,
    FrozenKnowledgeGraphSnapshot,
    KnowledgeGraphEvidenceProjection,
    KnowledgeGraphProjectionRequest,
    KnowledgeGraphQuery,
    KnowledgeIntelligenceResult,
    KnowledgeSourceCandidate,
    KnowledgeVerificationOutcome,
    MemoryBridgeProjection,
    MemoryBridgeRequest,
)


@runtime_checkable
class WebResearchSourcePort(Protocol):
    def retrieve(
        self,
        request: EngineeringKnowledgeRequest,
    ) -> tuple[KnowledgeSourceCandidate, ...]: ...


@runtime_checkable
class KnowledgeVerificationPort(Protocol):
    def verify(
        self,
        candidates: tuple[KnowledgeSourceCandidate, ...],
    ) -> KnowledgeVerificationOutcome: ...


@runtime_checkable
class KnowledgeIntelligencePort(Protocol):
    def retrieve(
        self,
        request: EngineeringKnowledgeRequest,
    ) -> KnowledgeIntelligenceResult: ...

    async def analyze_datasheet(
        self,
        request: DatasheetKnowledgeRequest,
    ) -> KnowledgeIntelligenceResult: ...

    def project_graph(
        self,
        request: KnowledgeGraphProjectionRequest,
    ) -> FrozenKnowledgeGraphSnapshot: ...

    def query_graph(
        self,
        request: KnowledgeGraphQuery,
    ) -> KnowledgeGraphEvidenceProjection: ...

    def project_memory_candidate(
        self,
        request: MemoryBridgeRequest,
    ) -> MemoryBridgeProjection: ...
