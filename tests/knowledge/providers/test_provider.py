from __future__ import annotations

from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.knowledge.providers.provider import KnowledgeProvider


class DuckProvider:
    provider_name = "duck"
    supported_sources = (KnowledgeSource.LOCAL,)

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        return []


def test_knowledge_provider_remains_runtime_structural_protocol() -> None:
    provider = DuckProvider()

    assert getattr(KnowledgeProvider, "_is_protocol", False) is True
    assert isinstance(provider, KnowledgeProvider)
    assert DuckProvider.__bases__ == (object,)
