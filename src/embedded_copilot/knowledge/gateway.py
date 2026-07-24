from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence

from embedded_copilot.knowledge.exceptions import (
    KnowledgeGatewayError,
    KnowledgeProviderError,
    ProviderInvalidResult,
)
from embedded_copilot.knowledge.github import GitHubSearchProvider
from embedded_copilot.knowledge.local import LocalKnowledgeProvider
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.knowledge.providers import KnowledgeProvider
from embedded_copilot.knowledge.providers.provider_registry import ProviderRegistry
from embedded_copilot.knowledge.web import WebSearchProvider


_SOURCE_PRIORITY = {
    KnowledgeSource.LOCAL: 0,
    KnowledgeSource.GITHUB: 1,
    KnowledgeSource.WEB: 2,
}


class KnowledgeGateway:
    """Own unified candidate ranking, deduplication, and global top-k."""

    def __init__(
        self,
        providers: Sequence[KnowledgeProvider] | None = None,
    ) -> None:
        active_providers: Sequence[KnowledgeProvider] = (
            providers
            if providers is not None
            else (
                LocalKnowledgeProvider(),
                GitHubSearchProvider(),
                WebSearchProvider(),
            )
        )
        try:
            self._registry = ProviderRegistry(active_providers)
        except Exception as exc:
            raise KnowledgeGatewayError(
                "knowledge provider configuration failed"
            ) from exc

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        try:
            candidates = self._registry.search(query)
        except ProviderInvalidResult as exc:
            if str(exc) == "provider modified query":
                raise KnowledgeGatewayError(
                    "knowledge provider modified query"
                ) from exc
            raise KnowledgeGatewayError("knowledge provider search failed") from exc
        except Exception as exc:
            raise KnowledgeGatewayError("knowledge provider search failed") from exc

        ranked = list(enumerate(candidates))
        ranked.sort(key=_ranking_key)
        deduplicated: list[KnowledgeResult] = []
        seen_results: set[tuple[KnowledgeSource, str]] = set()
        for _, result in ranked:
            key = (result.source, result.id)
            if key in seen_results:
                continue
            seen_results.add(key)
            deduplicated.append(result)
            if len(deduplicated) == query.top_k:
                break
        return deduplicated


class KnowledgeGatewayAdapter:
    """String-query adapter compatible with the existing retriever protocol."""

    def __init__(
        self,
        gateway: KnowledgeGateway,
        local_provider: LocalKnowledgeProvider,
        *,
        sources: Sequence[KnowledgeSource] = (),
        top_k: int = 4,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        configuration = KnowledgeQuery(
            query="adapter configuration",
            sources=list(sources),
            top_k=top_k,
            metadata=copy.deepcopy(dict(metadata or {})),
        )
        self._gateway = gateway
        self._local_provider = local_provider
        self._sources = tuple(configuration.sources)
        self._top_k = configuration.top_k
        self._metadata = copy.deepcopy(configuration.metadata)

    def search(self, query: str) -> Sequence[KnowledgeResult]:
        request = KnowledgeQuery(
            query=query,
            sources=list(self._sources),
            top_k=self._top_k,
            metadata=copy.deepcopy(self._metadata),
        )
        return self._gateway.search(request)

    def add_documents(self, documents: Sequence[object]) -> None:
        try:
            self._local_provider.add_documents(documents)
        except KnowledgeProviderError:
            raise
        except Exception as exc:
            raise KnowledgeProviderError("local document ingestion failed") from exc


def _ranking_key(
    item: tuple[int, KnowledgeResult],
) -> tuple[bool, float, int, int]:
    candidate_index, result = item
    return (
        result.score is None,
        -(result.score if result.score is not None else 0.0),
        _SOURCE_PRIORITY[result.source],
        candidate_index,
    )
