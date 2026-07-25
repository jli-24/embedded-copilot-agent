from __future__ import annotations

from collections.abc import Sequence

from embedded_copilot.knowledge.source import KnowledgeEvidence
from embedded_copilot.schemas.knowledge_trace import (
    KnowledgeTrace,
    KnowledgeTraceAction,
)


def build_knowledge_trace(
    *,
    query: str,
    evidence: Sequence[KnowledgeEvidence],
) -> KnowledgeTrace:
    source_ids = tuple(item.source_id for item in evidence)
    return KnowledgeTrace(
        query=query,
        source_ids=source_ids,
        result_count=len(source_ids),
        action=KnowledgeTraceAction.VIEWED,
    )
