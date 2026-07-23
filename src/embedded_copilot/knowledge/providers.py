from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from embedded_copilot.knowledge.exceptions import KnowledgeProviderError
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


class _OfflineFixtureProvider:
    """Shared deterministic implementation for explicitly injected fixtures."""

    provider_name: str
    supported_sources: tuple[KnowledgeSource, ...]

    def __init__(
        self,
        responses: Mapping[str, Sequence[KnowledgeResult]] | None,
        *,
        provider_name: str,
        source: KnowledgeSource,
    ) -> None:
        self.provider_name = provider_name
        self.supported_sources = (source,)
        self._source = source
        self._responses: dict[str, tuple[KnowledgeResult, ...]] = {}
        try:
            for raw_query, results in (responses or {}).items():
                if not isinstance(raw_query, str) or not raw_query.strip():
                    raise ValueError("fixture query must be a non-empty string")
                validated: list[KnowledgeResult] = []
                for result in results:
                    if not isinstance(result, KnowledgeResult):
                        raise TypeError("fixture result has an invalid type")
                    if result.source is not source:
                        raise ValueError("fixture result source does not match provider")
                    validated.append(_revalidate_result(result))
                self._responses[raw_query.strip()] = tuple(validated)
        except Exception as exc:
            raise KnowledgeProviderError(
                f"{provider_name} provider fixture validation failed"
            ) from exc

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        try:
            results: list[KnowledgeResult] = []
            for fixture in self._responses.get(query.query, ())[: query.top_k]:
                validated = _revalidate_result(fixture)
                if validated.source is not self._source:
                    raise ValueError("fixture result source does not match provider")
                results.append(
                    KnowledgeResult.model_validate(
                        {
                            **validated.model_dump(mode="python"),
                            "metadata": {
                                **validated.metadata,
                                "provider": self.provider_name,
                            },
                        }
                    )
                )
            return results
        except KnowledgeProviderError:
            raise
        except Exception as exc:
            raise KnowledgeProviderError(
                f"{self.provider_name} provider search failed"
            ) from exc


def _revalidate_result(result: KnowledgeResult) -> KnowledgeResult:
    return KnowledgeResult.model_validate(result.model_dump(mode="python"))
