from __future__ import annotations

import copy
from pathlib import PurePath
from typing import TYPE_CHECKING, Protocol

from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)

if TYPE_CHECKING:
    from embedded_copilot.rag.retriever import RetrievedChunk


class KnowledgeCandidateRetriever(Protocol):
    def retrieve(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...


class KnowledgeGatewayPort(Protocol):
    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...


class HybridRetrieverPort(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]: ...


class GatewayKnowledgeRetriever:
    def __init__(self, gateway: KnowledgeGatewayPort) -> None:
        self._gateway = gateway

    def retrieve(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        isolated = KnowledgeQuery.model_validate(
            copy.deepcopy(query.model_dump(mode="python"))
        )
        raw_results = self._gateway.search(isolated)
        return [
            KnowledgeResult.model_validate(
                copy.deepcopy(result.model_dump(mode="python"))
            )
            for result in raw_results
        ]


class HybridKnowledgeRetriever:
    def __init__(
        self,
        retriever: HybridRetrieverPort,
        *,
        score_threshold: float,
    ) -> None:
        if not 0 <= score_threshold <= 1:
            raise ValueError("score threshold is invalid")
        self._retriever = retriever
        self._score_threshold = score_threshold

    def retrieve(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        isolated = KnowledgeQuery.model_validate(
            copy.deepcopy(query.model_dump(mode="python"))
        )
        chunks = self._retriever.retrieve(
            isolated.query,
            top_k=isolated.top_k,
            score_threshold=self._score_threshold,
        )
        return [self._map_chunk(chunk) for chunk in chunks]

    @staticmethod
    def _map_chunk(chunk: RetrievedChunk) -> KnowledgeResult:
        validated = copy.deepcopy(chunk)
        document_type = (validated.metadata.document_type or "").casefold()
        source_type = {
            "datasheet": "datasheet",
            "official_doc": "official_doc",
        }.get(document_type, "user_upload")
        return KnowledgeResult(
            id=validated.chunk_id,
            title=PurePath(validated.citation.filename).name,
            content=validated.text,
            source=KnowledgeSource.LOCAL,
            score=validated.citation.score,
            metadata={"source_type": source_type},
        )
