from __future__ import annotations

import inspect
import traceback

import pytest

from embedded_copilot.knowledge.exceptions import (
    GitHubRateLimitError,
    ProviderInvalidResult,
    ProviderUnavailable,
)
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.knowledge.github import GitHubSearchProvider
from embedded_copilot.knowledge.github.client import FakeGitHubClient
from embedded_copilot.knowledge.github.models import (
    GitHubCodeItem,
    GitHubIssueItem,
    GitHubReleaseItem,
    GitHubRepositoryItem,
)
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeSource
from embedded_copilot.knowledge.providers import (
    GitHubSearchProvider as CompatibleGitHubSearchProvider,
)
from embedded_copilot.knowledge.providers.github import GitHubKnowledgeProvider
from embedded_copilot.knowledge.providers.provider import KnowledgeProvider


def _repository(
    identifier: str = "repo-1",
    *,
    score: float = 0.7,
    summary: str = "Official embedded examples.",
    reference_url: str = "https://github.com/espressif/esp-idf",
    domain: str = "firmware",
) -> GitHubRepositoryItem:
    return GitHubRepositoryItem(
        id=identifier,
        title="ESP-IDF examples",
        repository="espressif/esp-idf",
        owner="espressif",
        summary=summary,
        reference_url=reference_url,
        language="C",
        stars=100,
        score=score,
        category="repository",
        domain=domain,
    )


def _code() -> GitHubCodeItem:
    return GitHubCodeItem(
        id="code-1",
        title="SPI example",
        repository="espressif/esp-idf",
        owner="espressif",
        path="examples/peripherals/spi/main.c",
        summary="SPI example file guidance.",
        reference_url="https://github.com/espressif/esp-idf",
        language="C",
        score=0.8,
        category="example",
        domain="firmware",
    )


def _issue() -> GitHubIssueItem:
    return GitHubIssueItem(
        id="issue-7",
        title="Driver compile error",
        repository="vendor/sdk",
        owner="vendor",
        summary="Observed compile failure in the driver example.",
        reference_url="https://github.com/vendor/sdk/issues/7",
        score=0.9,
        category="issue",
        domain="debug",
    )


def _release() -> GitHubReleaseItem:
    return GitHubReleaseItem(
        id="release-v2",
        title="SDK v2.0",
        repository="vendor/sdk",
        owner="vendor",
        tag="v2.0",
        summary="Deterministic release notes.",
        reference_url="https://github.com/vendor/sdk/releases/v2.0",
        score=0.6,
        category="release",
        domain="firmware",
    )


def _all_client(query: str = "embedded") -> FakeGitHubClient:
    return FakeGitHubClient(
        repositories={query: [_repository()]},
        code={query: [_code()]},
        issues={query: [_issue()]},
        releases={query: [_release()]},
    )


def _exception_chain_text(error: BaseException) -> str:
    messages: list[str] = []
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        messages.append(str(current))
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return "\n".join(messages)


def test_github_provider_contract_and_compatibility_imports() -> None:
    provider = GitHubKnowledgeProvider()

    assert isinstance(provider, KnowledgeProvider)
    assert provider.provider_name == "github"
    assert provider.supported_sources == (KnowledgeSource.GITHUB,)
    assert CompatibleGitHubSearchProvider is GitHubSearchProvider


def test_client_none_returns_empty_candidates_without_gateway_error() -> None:
    provider = GitHubKnowledgeProvider()
    query = KnowledgeQuery(query="ESP32", sources=["GITHUB"])

    assert provider.search(query) == []
    assert KnowledgeGateway([provider]).search(query) == []


def test_explicit_github_types_win_and_use_fixed_call_order() -> None:
    client = _all_client()
    provider = GitHubKnowledgeProvider(client)

    results = provider.search(
        KnowledgeQuery(
            query="embedded",
            metadata={
                "github_types": ["release", "issue", "code", "repository"]
            },
        )
    )

    assert client.calls == [
        ("repository", "embedded"),
        ("code", "embedded"),
        ("issue", "embedded"),
        ("release", "embedded"),
    ]
    assert [result.id for result in results] == [
        "github:repository:repo-1",
        "github:code:code-1",
        "github:issue:issue-7",
        "github:release:release-v2",
    ]


@pytest.mark.parametrize(
    ("query", "metadata", "expected_call"),
    [
        ("release compile error", {"domains": ["firmware"]}, "code"),
        ("SDK changelog", {}, "release"),
        ("driver compile error", {}, "issue"),
        ("SPI example", {}, "code"),
        ("ESP32 camera", {}, "repository"),
    ],
)
def test_type_selection_precedence_is_deterministic(
    query: str,
    metadata: dict[str, object],
    expected_call: str,
) -> None:
    client = _all_client(query)

    GitHubKnowledgeProvider(client).search(
        KnowledgeQuery(query=query, metadata=metadata)
    )

    assert client.calls == [(expected_call, query)]


def test_repository_mapping_is_bounded_and_has_allowlisted_metadata() -> None:
    long_summary = "  alpha\n" + ("x" * 2500) + " SECRET_TAIL "
    client = FakeGitHubClient(
        repositories={"ESP32": [_repository(summary=long_summary)]}
    )

    result = GitHubKnowledgeProvider(client).search(
        KnowledgeQuery(query="ESP32")
    )[0]

    assert result.source is KnowledgeSource.GITHUB
    assert len(result.content) == 2000
    assert result.content == ("alpha " + ("x" * 2500))[:2000]
    assert "SECRET_TAIL" not in result.content
    assert result.metadata == {
        "repository": "espressif/esp-idf",
        "owner": "espressif",
        "language": "C",
        "stars": 100,
        "document_type": "repository",
        "reference_url": "https://github.com/espressif/esp-idf",
        "category": "repository",
        "domain": "firmware",
    }


def test_code_issue_and_release_mapping_do_not_include_raw_source() -> None:
    results = GitHubKnowledgeProvider(_all_client()).search(
        KnowledgeQuery(
            query="embedded",
            metadata={"github_types": ["code", "issue", "release"]},
        )
    )

    assert [result.metadata["document_type"] for result in results] == [
        "code",
        "issue",
        "release",
    ]
    assert results[0].content == "SPI example file guidance."
    assert "main.c" not in results[0].content
    assert all(
        set(result.metadata)
        <= {
            "repository",
            "owner",
            "language",
            "stars",
            "document_type",
            "reference_url",
            "category",
            "domain",
        }
        for result in results
    )


@pytest.mark.parametrize(
    "reference_url",
    [
        "http://github.com/vendor/sdk",
        "https://example.com/vendor/sdk",
        "https://github.com/vendor/sdk?token=SECRET_SENTINEL",
        "https://github.com/vendor/sdk#fragment",
        "https://user@github.com/vendor/sdk",
        "https://github.com/vendor/sdk/pulls/1",
    ],
)
def test_provider_rejects_unsafe_reference_url(reference_url: str) -> None:
    client = FakeGitHubClient(
        repositories={"ESP32": [_repository(reference_url=reference_url)]}
    )

    with pytest.raises(
        ProviderInvalidResult,
        match="GitHub provider result is invalid",
    ) as captured:
        GitHubKnowledgeProvider(client).search(KnowledgeQuery(query="ESP32"))

    assert "SECRET_SENTINEL" not in str(captured.value)


@pytest.mark.parametrize("github_types", [[], ["unknown"], "issue"])
def test_provider_rejects_invalid_explicit_github_types(
    github_types: object,
) -> None:
    with pytest.raises(
        ProviderInvalidResult,
        match="GitHub provider query is invalid",
    ):
        GitHubKnowledgeProvider(_all_client()).search(
            KnowledgeQuery(
                query="embedded",
                metadata={"github_types": github_types},
            )
        )


class MalformedClient:
    def search_repositories(self, query: str) -> object:
        return ("not", "a", "list")

    def search_code(self, query: str) -> list[GitHubCodeItem]:
        return []

    def search_issues(self, query: str) -> list[GitHubIssueItem]:
        return []

    def get_release(self, query: str) -> list[GitHubReleaseItem]:
        return []


def test_provider_rejects_malformed_client_response() -> None:
    with pytest.raises(
        ProviderInvalidResult,
        match="GitHub provider result is invalid",
    ):
        GitHubKnowledgeProvider(MalformedClient()).search(  # type: ignore[arg-type]
            KnowledgeQuery(query="ESP32")
        )


class FailingClient(MalformedClient):
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.token_provider = lambda: "SECRET_SENTINEL"

    def search_repositories(self, query: str) -> object:
        raise self.error


@pytest.mark.parametrize(
    "error",
    [
        GitHubRateLimitError("token=SECRET_SENTINEL"),
        RuntimeError("https://github.com/search?q=SECRET_SENTINEL"),
    ],
)
def test_provider_maps_client_failure_without_token_or_url_leak(
    error: Exception,
) -> None:
    with pytest.raises(ProviderUnavailable) as captured:
        GitHubKnowledgeProvider(FailingClient(error)).search(  # type: ignore[arg-type]
            KnowledgeQuery(query="ESP32")
        )

    assert str(captured.value) in {
        "GitHub rate limit exceeded",
        "GitHub provider is unavailable",
    }
    rendered = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "SECRET_SENTINEL" not in rendered
    assert "SECRET_SENTINEL" not in _exception_chain_text(captured.value)


def test_provider_rejects_credential_marker_in_candidate_content() -> None:
    client = FakeGitHubClient(
        repositories={
            "ESP32": [
                _repository(summary="Bearer SECRET_SENTINEL must not escape")
            ]
        }
    )

    with pytest.raises(ProviderInvalidResult) as captured:
        GitHubKnowledgeProvider(client).search(KnowledgeQuery(query="ESP32"))

    assert str(captured.value) == "GitHub provider result is invalid"
    assert "SECRET_SENTINEL" not in str(captured.value)


def test_provider_constructor_has_no_token_parameter() -> None:
    assert "token" not in str(inspect.signature(GitHubKnowledgeProvider.__init__))


def test_provider_keeps_candidate_order_and_gateway_owns_top_k() -> None:
    provider = GitHubKnowledgeProvider(
        FakeGitHubClient(
            repositories={
                "ESP32": [
                    _repository("low", score=0.1),
                    _repository("high", score=0.9),
                ]
            }
        )
    )
    query = KnowledgeQuery(query="ESP32", top_k=1)

    assert [result.id for result in provider.search(query)] == [
        "github:repository:low",
        "github:repository:high",
    ]
    assert [result.id for result in KnowledgeGateway([provider]).search(query)] == [
        "github:repository:high"
    ]


def test_provider_source_has_no_ranking_or_network_implementation() -> None:
    source = inspect.getsource(GitHubKnowledgeProvider).casefold()

    for forbidden in (
        ".sort(",
        "sorted(",
        "dedup",
        "top_k",
        "requests",
        "httpx",
        "urllib",
    ):
        assert forbidden not in source
