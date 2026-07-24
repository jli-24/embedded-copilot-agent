from __future__ import annotations

import pytest

from embedded_copilot.knowledge.exceptions import (
    ProviderInvalidResult,
    ProviderUnavailable,
)
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.knowledge.providers.provider_registry import ProviderRegistry


def _result(
    identifier: str,
    source: KnowledgeSource,
    score: float,
) -> KnowledgeResult:
    return KnowledgeResult(
        id=identifier,
        title=f"{identifier} title",
        content=f"{identifier} synthetic content",
        source=source,
        score=score,
        metadata={"category": "synthetic"},
    )


class RecordingProvider:
    def __init__(
        self,
        name: str,
        source: KnowledgeSource,
        results: object,
    ) -> None:
        self.provider_name = name
        self.supported_sources = (source,)
        self.results = results
        self.calls: list[KnowledgeQuery] = []

    def search(self, query: KnowledgeQuery) -> object:
        self.calls.append(query)
        return self.results


def test_registry_merges_all_candidates_without_ranking_or_top_k() -> None:
    first = RecordingProvider(
        "first",
        KnowledgeSource.LOCAL,
        [
            _result("first-low", KnowledgeSource.LOCAL, 0.1),
            _result("first-high", KnowledgeSource.LOCAL, 0.9),
        ],
    )
    second = RecordingProvider(
        "second",
        KnowledgeSource.GITHUB,
        [_result("second", KnowledgeSource.GITHUB, 1.0)],
    )
    registry = ProviderRegistry([first, second])

    results = registry.search(KnowledgeQuery(query="SPI", top_k=1))

    assert [result.id for result in results] == [
        "first-low",
        "first-high",
        "second",
    ]
    assert len(first.calls) == len(second.calls) == 1


def test_registry_filters_sources_before_calling_provider() -> None:
    local = RecordingProvider("local", KnowledgeSource.LOCAL, [])
    github = RecordingProvider("github", KnowledgeSource.GITHUB, [])
    registry = ProviderRegistry([local, github])

    registry.search(
        KnowledgeQuery(query="SPI", sources=[KnowledgeSource.GITHUB])
    )

    assert local.calls == []
    assert len(github.calls) == 1


def test_registry_remove_and_reregister_append_in_stable_order() -> None:
    first = RecordingProvider(
        "first",
        KnowledgeSource.LOCAL,
        [_result("first", KnowledgeSource.LOCAL, 1.0)],
    )
    second = RecordingProvider(
        "second",
        KnowledgeSource.GITHUB,
        [_result("second", KnowledgeSource.GITHUB, 1.0)],
    )
    registry = ProviderRegistry([first, second])

    assert registry.remove(" first ") is first
    registry.register(first)

    assert [item.id for item in registry.search(KnowledgeQuery(query="SPI"))] == [
        "second",
        "first",
    ]
    with pytest.raises(ProviderUnavailable, match="provider is unavailable"):
        registry.remove("missing")


class StatefulContractProvider:
    def __init__(self) -> None:
        self.fail_contract_access = False

    @property
    def provider_name(self) -> str:
        if self.fail_contract_access:
            raise RuntimeError("C:/Users/private/SECRET_SENTINEL")
        return "stateful"

    @property
    def supported_sources(self) -> tuple[KnowledgeSource, ...]:
        if self.fail_contract_access:
            raise RuntimeError("C:/Users/private/SECRET_SENTINEL")
        return (KnowledgeSource.LOCAL,)

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        return []


def test_registry_snapshots_provider_contract_for_lifecycle_operations() -> None:
    provider = StatefulContractProvider()
    registry = ProviderRegistry([provider])
    provider.fail_contract_access = True

    assert registry.search(KnowledgeQuery(query="SPI")) == []
    assert registry.remove("stateful") is provider


@pytest.mark.parametrize("name", ["", " Local ", "LOCAL", "C:/private"])
def test_registry_rejects_unsafe_or_noncanonical_provider_name(name: str) -> None:
    provider = RecordingProvider(name, KnowledgeSource.LOCAL, [])

    with pytest.raises(ProviderInvalidResult, match="configuration is invalid"):
        ProviderRegistry([provider])


def test_registry_rejects_duplicate_provider_name() -> None:
    first = RecordingProvider("local", KnowledgeSource.LOCAL, [])
    duplicate = RecordingProvider("local", KnowledgeSource.LOCAL, [])

    with pytest.raises(ProviderInvalidResult, match="configuration is invalid"):
        ProviderRegistry([first, duplicate])


class MutatingProvider(RecordingProvider):
    def search(self, query: KnowledgeQuery) -> object:
        query.metadata["filters"]["chip"] = "STM32"  # type: ignore[index]
        return []


def test_registry_rejects_query_mutation_and_isolates_caller() -> None:
    query = KnowledgeQuery(
        query="SPI",
        metadata={"filters": {"chip": "ESP32"}},
    )
    before = query.model_dump(mode="json")
    registry = ProviderRegistry(
        [MutatingProvider("local", KnowledgeSource.LOCAL, [])]
    )

    with pytest.raises(ProviderInvalidResult, match="modified query"):
        registry.search(query)

    assert query.model_dump(mode="json") == before


def test_registry_maps_unserializable_query_snapshot_safely() -> None:
    query = KnowledgeQuery(query="SPI", metadata={"opaque": object()})
    registry = ProviderRegistry(
        [RecordingProvider("local", KnowledgeSource.LOCAL, [])]
    )

    with pytest.raises(ProviderInvalidResult) as captured:
        registry.search(query)

    assert str(captured.value) == "provider query is invalid"


class UnserializableMutationProvider(RecordingProvider):
    def search(self, query: KnowledgeQuery) -> object:
        query.metadata["opaque"] = object()
        return []


def test_registry_maps_unserializable_provider_mutation_safely() -> None:
    registry = ProviderRegistry(
        [UnserializableMutationProvider("local", KnowledgeSource.LOCAL, [])]
    )

    with pytest.raises(ProviderInvalidResult) as captured:
        registry.search(KnowledgeQuery(query="SPI"))

    assert str(captured.value) == "provider modified query"


@pytest.mark.parametrize(
    "results",
    [(), {"not": "a list"}, type("ListSubclass", (list,), {})(), [object()]],
)
def test_registry_rejects_malformed_provider_result(results: object) -> None:
    registry = ProviderRegistry(
        [RecordingProvider("local", KnowledgeSource.LOCAL, results)]
    )

    with pytest.raises(ProviderInvalidResult, match="result is invalid"):
        registry.search(KnowledgeQuery(query="SPI"))


def test_registry_rejects_result_from_unsupported_source() -> None:
    registry = ProviderRegistry(
        [
            RecordingProvider(
                "local",
                KnowledgeSource.LOCAL,
                [_result("wrong", KnowledgeSource.WEB, 1.0)],
            )
        ]
    )

    with pytest.raises(ProviderInvalidResult, match="result is invalid"):
        registry.search(KnowledgeQuery(query="SPI"))


class MultiSourceProvider(RecordingProvider):
    def __init__(self) -> None:
        super().__init__("multi", KnowledgeSource.LOCAL, [])
        self.supported_sources = (KnowledgeSource.LOCAL, KnowledgeSource.WEB)

    def search(self, query: KnowledgeQuery) -> object:
        return [_result("web", KnowledgeSource.WEB, 1.0)]


def test_registry_rejects_candidate_outside_query_source_filter() -> None:
    registry = ProviderRegistry([MultiSourceProvider()])

    with pytest.raises(ProviderInvalidResult, match="result is invalid"):
        registry.search(
            KnowledgeQuery(query="SPI", sources=[KnowledgeSource.LOCAL])
        )


class FailingProvider(RecordingProvider):
    def search(self, query: KnowledgeQuery) -> object:
        raise RuntimeError("C:/Users/private/SECRET_SENTINEL")


def test_registry_maps_unexpected_provider_exception_without_leak() -> None:
    registry = ProviderRegistry(
        [FailingProvider("local", KnowledgeSource.LOCAL, [])]
    )

    with pytest.raises(ProviderUnavailable, match="provider is unavailable") as exc:
        registry.search(KnowledgeQuery(query="SPI"))

    assert "Users" not in str(exc.value)
    assert "SECRET_SENTINEL" not in str(exc.value)


def test_registry_fails_fast_without_calling_later_providers() -> None:
    failing = FailingProvider("first", KnowledgeSource.LOCAL, [])
    later = RecordingProvider("later", KnowledgeSource.GITHUB, [])
    registry = ProviderRegistry([failing, later])

    with pytest.raises(ProviderUnavailable, match="provider is unavailable"):
        registry.search(KnowledgeQuery(query="SPI"))

    assert later.calls == []


class UnavailableProvider(RecordingProvider):
    def search(self, query: KnowledgeQuery) -> object:
        raise ProviderUnavailable("provider is unavailable")


def test_registry_preserves_safe_provider_error_category() -> None:
    registry = ProviderRegistry(
        [UnavailableProvider("local", KnowledgeSource.LOCAL, [])]
    )

    with pytest.raises(ProviderUnavailable, match="provider is unavailable"):
        registry.search(KnowledgeQuery(query="SPI"))


class LeakingUnavailableProvider(RecordingProvider):
    def search(self, query: KnowledgeQuery) -> object:
        raise ProviderUnavailable("C:/Users/private/SECRET_SENTINEL")


def test_registry_sanitizes_classified_provider_error_text() -> None:
    registry = ProviderRegistry(
        [LeakingUnavailableProvider("local", KnowledgeSource.LOCAL, [])]
    )

    with pytest.raises(ProviderUnavailable) as captured:
        registry.search(KnowledgeQuery(query="SPI"))

    assert str(captured.value) == "provider is unavailable"


class LeakingInvalidResultProvider(RecordingProvider):
    def search(self, query: KnowledgeQuery) -> object:
        raise ProviderInvalidResult("C:/Users/private/SECRET_SENTINEL")


def test_registry_sanitizes_provider_invalid_result_text() -> None:
    registry = ProviderRegistry(
        [LeakingInvalidResultProvider("local", KnowledgeSource.LOCAL, [])]
    )

    with pytest.raises(ProviderInvalidResult) as captured:
        registry.search(KnowledgeQuery(query="SPI"))

    assert str(captured.value) == "provider result is invalid"


class LeakingConfigurationProvider:
    @property
    def provider_name(self) -> str:
        raise ProviderUnavailable("C:/Users/private/SECRET_SENTINEL")

    supported_sources = (KnowledgeSource.LOCAL,)

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        return []


def test_registry_sanitizes_classified_configuration_error_text() -> None:
    with pytest.raises(ProviderUnavailable) as captured:
        ProviderRegistry([LeakingConfigurationProvider()])

    assert str(captured.value) == "provider is unavailable"


def test_registry_returns_deeply_isolated_result_copies() -> None:
    original = _result("local", KnowledgeSource.LOCAL, 1.0)
    registry = ProviderRegistry(
        [RecordingProvider("local", KnowledgeSource.LOCAL, [original])]
    )

    result = registry.search(KnowledgeQuery(query="SPI"))[0]
    original.metadata["category"] = "mutated"

    assert result.metadata == {"category": "synthetic"}
