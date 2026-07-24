from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)


@runtime_checkable
class KnowledgeProvider(Protocol):
    provider_name: str
    supported_sources: tuple[KnowledgeSource, ...]

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...
