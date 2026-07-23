from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence

from embedded_copilot.knowledge.exceptions import (
    KnowledgeGatewayError,
    KnowledgeProviderError,
)
from embedded_copilot.knowledge.github import GitHubSearchProvider
from embedded_copilot.knowledge.local import LocalKnowledgeProvider
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.knowledge.providers import KnowledgeProvider
from embedded_copilot.knowledge.web import WebSearchProvider


_PROVIDER_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
_SOURCE_PRIORITY = {
    KnowledgeSource.LOCAL: 0,
    KnowledgeSource.GITHUB: 1,
    KnowledgeSource.WEB: 2,
}


class KnowledgeGateway:
    """Deterministic, sequential scheduler for explicitly configured providers."""

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
            seen_names: set[str] = set()
            validated: list[KnowledgeProvider] = []
            for provider in active_providers:
                if not isinstance(provider, KnowledgeProvider):
                    raise TypeError("provider does not implement the protocol")
                raw_name = provider.provider_name
                if not isinstance(raw_name, str):
                    raise TypeError("provider name must be a string")
                normalized_name = raw_name.strip().casefold()
                if (
                    raw_name != normalized_name
                    or not _PROVIDER_NAME.fullmatch(normalized_name)
                ):
                    raise ValueError("provider name is not safe")
                if normalized_name in seen_names:
                    raise ValueError("provider name is duplicated")
                sources = provider.supported_sources
                if not sources or any(
                    not isinstance(source, KnowledgeSource) for source in sources
                ):
                    raise ValueError("provider sources are invalid")
                seen_names.add(normalized_name)
                validated.append(provider)
            self._providers = tuple(validated)
        except Exception as exc:
            raise KnowledgeGatewayError(
                "knowledge provider configuration failed"
            ) from exc

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        requested_sources = set(query.sources)
        ranked: list[tuple[KnowledgeResult, int, int]] = []
        for provider_index, provider in enumerate(self._providers):
            if requested_sources and requested_sources.isdisjoint(
                provider.supported_sources
            ):
                continue
            provider_query = query.model_copy(deep=True)
            before = provider_query.model_dump(mode="python")
            try:
                raw_results = provider.search(provider_query)
            except Exception as exc:
                raise KnowledgeGatewayError(
                    "knowledge provider search failed"
                ) from exc
            after = provider_query.model_dump(mode="python")
            if after != before:
                raise KnowledgeGatewayError("knowledge provider modified query")
            try:
                if not isinstance(raw_results, list):
                    raise TypeError("provider result must be a list")
                if len(raw_results) > query.top_k:
                    raise ValueError("provider exceeded query top_k")
                for result_index, result in enumerate(raw_results):
                    if not isinstance(result, KnowledgeResult):
                        raise TypeError("provider returned an invalid result")
                    validated = KnowledgeResult.model_validate(
                        result.model_dump(mode="python")
                    )
                    if validated.source not in provider.supported_sources:
                        raise ValueError("provider returned an unsupported source")
                    ranked.append((validated, provider_index, result_index))
            except Exception as exc:
                raise KnowledgeGatewayError(
                    "knowledge provider search failed"
                ) from exc

        ranked.sort(key=_ranking_key)
        deduplicated: list[KnowledgeResult] = []
        seen_results: set[tuple[KnowledgeSource, str]] = set()
        for result, _, _ in ranked:
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
    item: tuple[KnowledgeResult, int, int],
) -> tuple[bool, float, int, int, int]:
    result, provider_index, result_index = item
    return (
        result.score is None,
        -(result.score if result.score is not None else 0.0),
        _SOURCE_PRIORITY[result.source],
        provider_index,
        result_index,
    )
