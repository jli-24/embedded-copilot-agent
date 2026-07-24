import socket

import pytest

from embedded_copilot.knowledge.exceptions import KnowledgeProviderError
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.knowledge.github import GitHubSearchProvider
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.knowledge.providers import KnowledgeProvider
from embedded_copilot.knowledge.web import WebSearchProvider


def _result(
    result_id: str,
    source: KnowledgeSource,
    *,
    score: float | None = 1.0,
) -> KnowledgeResult:
    return KnowledgeResult(
        id=result_id,
        title=f"{result_id} title",
        content=f"{result_id} content",
        source=source,
        score=score,
        metadata={"license": "test"},
    )


def test_mock_providers_are_protocol_compatible_and_empty_by_default() -> None:
    query = KnowledgeQuery(query="SPI")
    web = WebSearchProvider()
    github = GitHubSearchProvider()

    assert isinstance(web, KnowledgeProvider)
    assert isinstance(github, KnowledgeProvider)
    assert web.provider_name == "web"
    assert web.supported_sources == (KnowledgeSource.WEB,)
    assert github.provider_name == "github"
    assert github.supported_sources == (KnowledgeSource.GITHUB,)
    assert web.search(query) == []
    assert github.search(query) == []


def test_web_provider_returns_only_exact_query_fixture_with_provider_metadata() -> None:
    fixture = _result("web-spi", KnowledgeSource.WEB)
    provider = WebSearchProvider({"SPI": [fixture]})

    result = provider.search(KnowledgeQuery(query="SPI"))[0]

    assert result.source is KnowledgeSource.WEB
    assert result.metadata == {"license": "test", "provider": "web"}
    assert provider.search(KnowledgeQuery(query="spi")) == []
    assert fixture.metadata == {"license": "test"}


def test_github_provider_returns_all_candidates_in_fixture_order() -> None:
    provider = GitHubSearchProvider(
        {
            "UART": [
                _result("one", KnowledgeSource.GITHUB),
                _result("two", KnowledgeSource.GITHUB),
                _result("three", KnowledgeSource.GITHUB),
            ]
        }
    )

    results = provider.search(KnowledgeQuery(query="UART", top_k=2))

    assert [result.id for result in results] == ["one", "two", "three"]
    assert all(result.metadata["provider"] == "github" for result in results)


def test_gateway_can_select_high_score_after_fixture_query_top_k() -> None:
    provider = GitHubSearchProvider(
        {
            "UART": [
                _result("low", KnowledgeSource.GITHUB, score=0.1),
                _result("high", KnowledgeSource.GITHUB, score=0.9),
            ]
        }
    )

    results = KnowledgeGateway([provider]).search(
        KnowledgeQuery(query="UART", top_k=1)
    )

    assert [result.id for result in results] == ["high"]


def test_mock_providers_treat_query_as_immutable() -> None:
    query = KnowledgeQuery(query="SPI", metadata={"filters": {"chip": "ESP32"}})
    original = query.model_dump(mode="json")
    provider = WebSearchProvider(
        {"SPI": [_result("web-spi", KnowledgeSource.WEB)]}
    )

    provider.search(query)

    assert query.model_dump(mode="json") == original


def test_mock_provider_rejects_fixture_with_wrong_source_safely() -> None:
    with pytest.raises(
        KnowledgeProviderError,
        match="web provider fixture validation failed",
    ) as captured:
        WebSearchProvider(
            {
                "SPI": [
                    _result(
                        "C:/Users/private/SECRET_SENTINEL",
                        KnowledgeSource.GITHUB,
                    )
                ]
            }
        )

    assert "Users" not in str(captured.value)
    assert "SECRET_SENTINEL" not in str(captured.value)


def test_mock_providers_do_not_use_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_socket(*args: object, **kwargs: object) -> object:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    web = WebSearchProvider(
        {"SPI": [_result("web-spi", KnowledgeSource.WEB)]}
    )
    github = GitHubSearchProvider(
        {"SPI": [_result("github-spi", KnowledgeSource.GITHUB)]}
    )

    assert web.search(KnowledgeQuery(query="SPI"))
    assert github.search(KnowledgeQuery(query="SPI"))
