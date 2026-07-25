from __future__ import annotations

import copy

from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeResult
from embedded_copilot.knowledge.retriever import KnowledgeCandidateRetriever
from embedded_copilot.knowledge.source import (
    KnowledgeEvidence,
    KnowledgeRetrieval,
    project_result,
)
from embedded_copilot.knowledge.trace import build_knowledge_trace


class KnowledgeIntelligenceError(RuntimeError):
    """Safe failure from candidate retrieval or projection."""


class KnowledgeManager:
    """Projects retrieval candidates without promoting engineering evidence."""

    def __init__(self, retriever: KnowledgeCandidateRetriever) -> None:
        self._retriever = retriever

    def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrieval:
        isolated = KnowledgeQuery.model_validate(
            copy.deepcopy(query.model_dump(mode="python"))
        )
        try:
            raw_results = self._retriever.retrieve(isolated)
            if type(raw_results) is not list:
                raise TypeError("retriever result must be a list")
            evidence: list[KnowledgeEvidence] = []
            seen: set[str] = set()
            for raw_result in raw_results:
                if not isinstance(raw_result, KnowledgeResult):
                    raise TypeError("knowledge candidate is invalid")
                result = KnowledgeResult.model_validate(
                    copy.deepcopy(raw_result.model_dump(mode="python"))
                )
                key = result.id.casefold()
                if key in seen:
                    continue
                seen.add(key)
                evidence.append(project_result(result))
        except Exception as exc:
            raise KnowledgeIntelligenceError("knowledge candidate is unsafe") from exc
        projected = tuple(evidence)
        return KnowledgeRetrieval(
            evidence=projected,
            trace=build_knowledge_trace(
                query=isolated.query,
                evidence=projected,
            ),
        )
