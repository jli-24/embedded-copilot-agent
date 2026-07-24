from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from dataclasses import dataclass

from embedded_copilot.knowledge.exceptions import (
    ProviderError,
    ProviderInvalidResult,
    ProviderUnavailable,
)
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.knowledge.providers.provider import KnowledgeProvider


_PROVIDER_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class _RegisteredProvider:
    name: str
    provider: KnowledgeProvider
    sources: tuple[KnowledgeSource, ...]


class ProviderRegistry:
    """Ordered provider lifecycle and candidate collection boundary."""

    def __init__(
        self,
        providers: Sequence[KnowledgeProvider] = (),
    ) -> None:
        self._providers: list[_RegisteredProvider] = []
        for provider in providers:
            self.register(provider)

    def register(self, provider: KnowledgeProvider) -> None:
        try:
            if not isinstance(provider, KnowledgeProvider):
                raise TypeError("provider does not implement the protocol")
            name = provider.provider_name
            if (
                not isinstance(name, str)
                or name != name.strip().casefold()
                or not _PROVIDER_NAME.fullmatch(name)
            ):
                raise ValueError("provider name is invalid")
            if any(item.name == name for item in self._providers):
                raise ValueError("provider name is duplicated")
            sources = provider.supported_sources
            if (
                not isinstance(sources, tuple)
                or not sources
                or any(not isinstance(source, KnowledgeSource) for source in sources)
                or len(set(sources)) != len(sources)
            ):
                raise ValueError("provider sources are invalid")
        except ProviderUnavailable as exc:
            raise ProviderUnavailable("provider is unavailable") from exc
        except ProviderInvalidResult as exc:
            raise ProviderInvalidResult(
                "provider configuration is invalid"
            ) from exc
        except ProviderError as exc:
            raise ProviderError("provider configuration failed") from exc
        except Exception as exc:
            raise ProviderInvalidResult(
                "provider configuration is invalid"
            ) from exc
        self._providers.append(
            _RegisteredProvider(
                name=name,
                provider=provider,
                sources=sources,
            )
        )

    def remove(self, name: str) -> KnowledgeProvider:
        normalized = name.strip().casefold() if isinstance(name, str) else ""
        for index, registration in enumerate(self._providers):
            if registration.name == normalized:
                return self._providers.pop(index).provider
        raise ProviderUnavailable("provider is unavailable")

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        try:
            validated_query = KnowledgeQuery.model_validate(
                copy.deepcopy(query.model_dump(mode="python"))
            )
        except Exception as exc:
            raise ProviderInvalidResult("provider query is invalid") from exc

        requested_sources = set(validated_query.sources)
        candidates: list[KnowledgeResult] = []
        for registration in self._providers:
            if requested_sources and requested_sources.isdisjoint(
                registration.sources
            ):
                continue
            provider = registration.provider
            try:
                provider_query = validated_query.model_copy(deep=True)
                before = provider_query.model_dump(mode="json")
            except Exception as exc:
                raise ProviderInvalidResult("provider query is invalid") from exc
            try:
                raw_results = provider.search(provider_query)
            except ProviderUnavailable as exc:
                raise ProviderUnavailable("provider is unavailable") from exc
            except ProviderInvalidResult as exc:
                raise ProviderInvalidResult("provider result is invalid") from exc
            except ProviderError as exc:
                raise ProviderError("provider search failed") from exc
            except Exception as exc:
                raise ProviderUnavailable("provider is unavailable") from exc
            try:
                after = provider_query.model_dump(mode="json")
            except Exception as exc:
                raise ProviderInvalidResult("provider modified query") from exc
            if after != before:
                raise ProviderInvalidResult("provider modified query")
            try:
                if type(raw_results) is not list:
                    raise TypeError("provider result must be a list")
                for result in raw_results:
                    if not isinstance(result, KnowledgeResult):
                        raise TypeError("provider result item is invalid")
                    validated = KnowledgeResult.model_validate(
                        copy.deepcopy(result.model_dump(mode="python"))
                    )
                    if validated.source not in registration.sources:
                        raise ValueError("provider result source is unsupported")
                    if (
                        requested_sources
                        and validated.source not in requested_sources
                    ):
                        raise ValueError("provider result source was not requested")
                    candidates.append(validated)
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderInvalidResult("provider result is invalid") from exc
        return candidates
