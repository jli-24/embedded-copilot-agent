import pytest

from embedded_copilot.knowledge.exceptions import KnowledgeGatewayError
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)


def _result(
    result_id: str,
    source: KnowledgeSource,
    score: float | None,
) -> KnowledgeResult:
    return KnowledgeResult(
        id=result_id,
        title=f"{result_id} title",
        content=f"{result_id} content",
        source=source,
        score=score,
    )


class _Provider:
    def __init__(
        self,
        name: str,
        source: KnowledgeSource,
        results: list[object] | None = None,
    ) -> None:
        self.provider_name = name
        self.supported_sources = (source,)
        self.results = list(results or [])
        self.queries: list[dict[str, object]] = []

    def search(self, query: KnowledgeQuery):
        self.queries.append(query.model_dump(mode="json"))
        return list(self.results)


def test_gateway_routes_selected_sources_and_empty_sources_call_all() -> None:
    local = _Provider("local", KnowledgeSource.LOCAL)
    github = _Provider("github", KnowledgeSource.GITHUB)
    web = _Provider("web", KnowledgeSource.WEB)
    gateway = KnowledgeGateway([local, github, web])

    gateway.search(KnowledgeQuery(query="SPI", sources=["LOCAL", "GITHUB"]))
    assert len(local.queries) == 1
    assert len(github.queries) == 1
    assert web.queries == []

    gateway.search(KnowledgeQuery(query="UART"))
    assert len(local.queries) == 2
    assert len(github.queries) == 2
    assert len(web.queries) == 1


def test_gateway_ranks_by_score_source_priority_and_stable_order() -> None:
    local = _Provider(
        "local",
        KnowledgeSource.LOCAL,
        [
            _result("local-two", KnowledgeSource.LOCAL, 2),
            _result("local-tie-a", KnowledgeSource.LOCAL, 1),
            _result("local-tie-b", KnowledgeSource.LOCAL, 1),
        ],
    )
    github = _Provider(
        "github",
        KnowledgeSource.GITHUB,
        [
            _result("github-three", KnowledgeSource.GITHUB, 3),
            _result("github-tie", KnowledgeSource.GITHUB, 1),
        ],
    )
    web = _Provider(
        "web",
        KnowledgeSource.WEB,
        [
            _result("web-tie", KnowledgeSource.WEB, 1),
            _result("web-none", KnowledgeSource.WEB, None),
        ],
    )

    results = KnowledgeGateway([local, github, web]).search(
        KnowledgeQuery(query="SPI", top_k=10)
    )

    assert [result.id for result in results] == [
        "github-three",
        "local-two",
        "local-tie-a",
        "local-tie-b",
        "github-tie",
        "web-tie",
        "web-none",
    ]


def test_gateway_deduplicates_by_source_and_id_then_enforces_global_top_k() -> None:
    local = _Provider(
        "local",
        KnowledgeSource.LOCAL,
        [
            _result("same", KnowledgeSource.LOCAL, 1),
            _result("same", KnowledgeSource.LOCAL, 3),
            _result("local-extra", KnowledgeSource.LOCAL, 2),
        ],
    )
    github = _Provider(
        "github",
        KnowledgeSource.GITHUB,
        [_result("same", KnowledgeSource.GITHUB, 2)],
    )

    results = KnowledgeGateway([local, github]).search(
        KnowledgeQuery(query="SPI", top_k=3)
    )

    assert [(result.source, result.id, result.score) for result in results] == [
        (KnowledgeSource.LOCAL, "same", 3.0),
        (KnowledgeSource.LOCAL, "local-extra", 2.0),
        (KnowledgeSource.GITHUB, "same", 2.0),
    ]


class _TooManyProvider(_Provider):
    def search(self, query: KnowledgeQuery):
        return [
            _result(f"result-{index}", KnowledgeSource.LOCAL, 1)
            for index in range(query.top_k + 1)
        ]


class _MutatingProvider(_Provider):
    def search(self, query: KnowledgeQuery):
        filters = query.metadata["filters"]
        assert isinstance(filters, dict)
        filters["chip"] = "STM32"
        return []


class _FailingProvider(_Provider):
    def search(self, query: KnowledgeQuery):
        raise RuntimeError("C:/Users/private/SECRET_SENTINEL")


@pytest.mark.parametrize(
    "provider",
    [
        _TooManyProvider("local", KnowledgeSource.LOCAL),
        _Provider("local", KnowledgeSource.LOCAL, [object()]),
        _FailingProvider("local", KnowledgeSource.LOCAL),
    ],
)
def test_gateway_fails_safely_for_invalid_provider_behavior(provider: object) -> None:
    with pytest.raises(
        KnowledgeGatewayError,
        match="knowledge provider search failed",
    ) as captured:
        KnowledgeGateway([provider]).search(KnowledgeQuery(query="SPI", top_k=1))

    assert "Users" not in str(captured.value)
    assert "SECRET_SENTINEL" not in str(captured.value)


def test_gateway_detects_query_mutation_without_mutating_caller_query() -> None:
    query = KnowledgeQuery(
        query="SPI",
        metadata={"filters": {"chip": "ESP32"}},
    )
    original = query.model_dump(mode="json")

    with pytest.raises(
        KnowledgeGatewayError,
        match="knowledge provider modified query",
    ):
        KnowledgeGateway(
            [_MutatingProvider("local", KnowledgeSource.LOCAL)]
        ).search(query)

    assert query.model_dump(mode="json") == original


def test_gateway_revalidates_mutated_result_metadata() -> None:
    result = _result("local", KnowledgeSource.LOCAL, 1)
    result.metadata["api_token"] = "SECRET_SENTINEL"

    with pytest.raises(
        KnowledgeGatewayError,
        match="knowledge provider search failed",
    ) as captured:
        KnowledgeGateway(
            [_Provider("local", KnowledgeSource.LOCAL, [result])]
        ).search(KnowledgeQuery(query="SPI"))

    assert "SECRET_SENTINEL" not in str(captured.value)


def test_gateway_rejects_duplicate_or_invalid_provider_configuration() -> None:
    with pytest.raises(
        KnowledgeGatewayError,
        match="knowledge provider configuration failed",
    ):
        KnowledgeGateway(
            [
                _Provider("local", KnowledgeSource.LOCAL),
                _Provider("LOCAL", KnowledgeSource.LOCAL),
            ]
        )

    invalid = _Provider("C:/private", KnowledgeSource.LOCAL)
    with pytest.raises(KnowledgeGatewayError):
        KnowledgeGateway([invalid])

    not_normalized = _Provider(" Local ", KnowledgeSource.LOCAL)
    with pytest.raises(KnowledgeGatewayError):
        KnowledgeGateway([not_normalized])


def test_default_gateway_is_offline_and_returns_empty_results() -> None:
    assert KnowledgeGateway().search(KnowledgeQuery(query="SPI")) == []
