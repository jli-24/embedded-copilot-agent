from __future__ import annotations

import copy

from embedded_copilot.datasheet_runtime import (
    DatasheetAnalysisTimeout,
    DatasheetIntelligencePort,
    DatasheetResponse,
)
from embedded_copilot.knowledge.intelligence.datasheet.service import (
    DatasheetCandidateProjector,
)
from embedded_copilot.knowledge.intelligence.exceptions import (
    KnowledgeDataRejected,
    KnowledgeObservationTimeout,
    KnowledgeSourceUnavailable,
)
from embedded_copilot.knowledge.intelligence.graph.service import (
    KnowledgeGraphProjector,
)
from embedded_copilot.knowledge.intelligence.memory_bridge.service import (
    KnowledgeMemoryBridge,
)
from embedded_copilot.knowledge.intelligence.models import (
    DatasheetKnowledgeRequest,
    EngineeringKnowledgeRequest,
    FrozenKnowledgeGraphSnapshot,
    KnowledgeGraphEvidenceProjection,
    KnowledgeGraphProjectionRequest,
    KnowledgeGraphQuery,
    KnowledgeIntelligenceResult,
    KnowledgeProgressTrace,
    KnowledgeSourceCandidate,
    KnowledgeVerificationOutcome,
    MemoryBridgeProjection,
    MemoryBridgeRequest,
)
from embedded_copilot.knowledge.intelligence.ports import (
    KnowledgeVerificationPort,
    WebResearchSourcePort,
)
from embedded_copilot.knowledge.source import KnowledgeSourceType


class _KnowledgeIntelligenceService:
    __slots__ = (
        "_datasheet_port",
        "_datasheet_projector",
        "_graph_projector",
        "_memory_bridge",
        "_verification_port",
        "_web_source",
    )

    def __init__(
        self,
        *,
        web_source: WebResearchSourcePort | None,
        datasheet_port: DatasheetIntelligencePort | None,
        verification_port: KnowledgeVerificationPort,
    ) -> None:
        self._web_source = web_source
        self._datasheet_port = datasheet_port
        self._verification_port = verification_port
        self._datasheet_projector = DatasheetCandidateProjector()
        self._graph_projector = KnowledgeGraphProjector()
        self._memory_bridge = KnowledgeMemoryBridge()

    def retrieve(
        self,
        request: EngineeringKnowledgeRequest,
    ) -> KnowledgeIntelligenceResult:
        checked = EngineeringKnowledgeRequest.model_validate(copy.deepcopy(request))
        if self._web_source is None:
            raise KnowledgeSourceUnavailable()
        try:
            raw_candidates = self._web_source.retrieve(checked)
        except TimeoutError:
            raise KnowledgeObservationTimeout() from None
        except Exception:
            raise KnowledgeSourceUnavailable() from None
        candidates = self._checked_candidates(raw_candidates)
        outcome = self._verify(candidates)
        return KnowledgeIntelligenceResult(
            verified_evidence=outcome.verified_evidence,
            rejected_count=outcome.rejected_count,
            review_required_count=outcome.review_required_count,
            trace=(
                KnowledgeProgressTrace(
                    sequence=1,
                    stage="source",
                    status="completed",
                    count=len(candidates),
                    source_type=KnowledgeSourceType.WEB,
                ),
                KnowledgeProgressTrace(
                    sequence=2,
                    stage="verification",
                    status="completed",
                    count=len(outcome.verified_evidence),
                    source_type=KnowledgeSourceType.WEB,
                ),
            ),
        )

    async def analyze_datasheet(
        self,
        request: DatasheetKnowledgeRequest,
    ) -> KnowledgeIntelligenceResult:
        checked = DatasheetKnowledgeRequest.model_validate(copy.deepcopy(request))
        if self._datasheet_port is None:
            raise KnowledgeSourceUnavailable()
        try:
            raw_response = await self._datasheet_port.analyze(
                checked.datasheet_request.model_copy(deep=True)
            )
            response = DatasheetResponse.model_validate(copy.deepcopy(raw_response))
        except (TimeoutError, DatasheetAnalysisTimeout):
            raise KnowledgeObservationTimeout() from None
        except Exception:
            raise KnowledgeSourceUnavailable() from None
        try:
            candidates = self._datasheet_projector.project(checked, response)
        except Exception:
            raise KnowledgeDataRejected() from None
        outcome = self._verify(candidates)
        return KnowledgeIntelligenceResult(
            verified_evidence=outcome.verified_evidence,
            rejected_count=outcome.rejected_count,
            review_required_count=outcome.review_required_count,
            trace=(
                KnowledgeProgressTrace(
                    sequence=1,
                    stage="datasheet",
                    status="completed",
                    count=len(candidates),
                    source_type=KnowledgeSourceType.DATASHEET,
                ),
                KnowledgeProgressTrace(
                    sequence=2,
                    stage="verification",
                    status="completed",
                    count=len(outcome.verified_evidence),
                    source_type=KnowledgeSourceType.DATASHEET,
                ),
            ),
        )

    def project_graph(
        self,
        request: KnowledgeGraphProjectionRequest,
    ) -> FrozenKnowledgeGraphSnapshot:
        return self._graph_projector.project(request)

    def query_graph(
        self,
        request: KnowledgeGraphQuery,
    ) -> KnowledgeGraphEvidenceProjection:
        return self._graph_projector.query(request)

    def project_memory_candidate(
        self,
        request: MemoryBridgeRequest,
    ) -> MemoryBridgeProjection:
        return self._memory_bridge.project(request)

    @staticmethod
    def _checked_candidates(value: object) -> tuple[KnowledgeSourceCandidate, ...]:
        if type(value) is not tuple:
            raise KnowledgeDataRejected()
        try:
            return tuple(
                KnowledgeSourceCandidate.model_validate(copy.deepcopy(item))
                for item in value
            )
        except Exception:
            raise KnowledgeDataRejected() from None

    def _verify(
        self,
        candidates: tuple[KnowledgeSourceCandidate, ...],
    ) -> KnowledgeVerificationOutcome:
        try:
            raw_outcome = self._verification_port.verify(candidates)
            if not isinstance(raw_outcome, KnowledgeVerificationOutcome):
                raise TypeError("knowledge verification result is invalid")
            return KnowledgeVerificationOutcome.model_validate(
                copy.deepcopy(raw_outcome)
            )
        except Exception:
            raise KnowledgeDataRejected() from None
