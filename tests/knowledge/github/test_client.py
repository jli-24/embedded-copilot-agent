from __future__ import annotations

import traceback

from pydantic import ValidationError
import pytest

import embedded_copilot.knowledge.github as github_package
import embedded_copilot.knowledge as knowledge_package
import embedded_copilot.knowledge.providers as providers_package
from embedded_copilot.knowledge.exceptions import ProviderInvalidResult
from embedded_copilot.knowledge.github.client import (
    FakeGitHubClient,
    GitHubClient,
)
from embedded_copilot.knowledge.github.models import (
    GitHubCodeItem,
    GitHubIssueItem,
    GitHubReleaseItem,
    GitHubRepositoryItem,
)


def _repository() -> GitHubRepositoryItem:
    return GitHubRepositoryItem(
        id="repo-1",
        title="ESP-IDF examples",
        repository="espressif/esp-idf",
        owner="espressif",
        summary="Official embedded examples.",
        reference_url="https://github.com/espressif/esp-idf",
        language="C",
        stars=100,
        score=0.7,
        category="repository",
        domain="firmware",
    )


def _code() -> GitHubCodeItem:
    return GitHubCodeItem(
        id="code-1",
        title="SPI example",
        repository="espressif/esp-idf",
        owner="espressif",
        path="examples/peripherals/spi/main.c",
        summary="SPI example file.",
        reference_url="https://github.com/espressif/esp-idf",
        language="C",
        score=0.8,
        category="example",
        domain="firmware",
    )


def _issue() -> GitHubIssueItem:
    return GitHubIssueItem(
        id="issue-1",
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
        id="release-1",
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


class DuckClient:
    def search_repositories(self, query: str) -> list[GitHubRepositoryItem]:
        return []

    def search_code(self, query: str) -> list[GitHubCodeItem]:
        return []

    def search_issues(self, query: str) -> list[GitHubIssueItem]:
        return []

    def get_release(self, query: str) -> list[GitHubReleaseItem]:
        return []


def test_github_client_is_runtime_structural_protocol() -> None:
    client = DuckClient()

    assert getattr(GitHubClient, "_is_protocol", False) is True
    assert isinstance(client, GitHubClient)
    assert DuckClient.__bases__ == (object,)


@pytest.mark.parametrize(
    ("model", "field"),
    [
        (_repository(), "title"),
        (_code(), "path"),
        (_issue(), "summary"),
        (_release(), "tag"),
    ],
)
def test_github_raw_models_are_frozen_and_forbid_extra(
    model: object,
    field: str,
) -> None:
    with pytest.raises(ValidationError):
        model.__class__.model_validate(
            {**model.model_dump(mode="python"), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        setattr(model, field, "changed")


def test_fake_client_returns_deep_copies_and_records_stable_calls() -> None:
    repository = _repository()
    code = _code()
    issue = _issue()
    release = _release()
    client = FakeGitHubClient(
        repositories={"ESP32": [repository]},
        code={"SPI": [code]},
        issues={"compile error": [issue]},
        releases={"SDK": [release]},
    )

    assert client.search_repositories("ESP32") == [repository]
    assert client.search_code("SPI") == [code]
    assert client.search_issues("compile error") == [issue]
    assert client.get_release("SDK") == [release]
    assert client.search_repositories("esp32") == []
    assert client.calls == [
        ("repository", "ESP32"),
        ("code", "SPI"),
        ("issue", "compile error"),
        ("release", "SDK"),
        ("repository", "esp32"),
    ]
    assert client.search_repositories("ESP32")[0] is not repository


@pytest.mark.parametrize("query", [" ESP32", "ESP32 ", "\tESP32"])
def test_fake_client_rejects_noncanonical_exact_query_keys(query: str) -> None:
    with pytest.raises(
        ProviderInvalidResult,
        match="GitHub client fixture is invalid",
    ):
        FakeGitHubClient(repositories={query: [_repository()]})


class FailingFixtureValues:
    def __iter__(self):
        raise RuntimeError("token=SECRET_SENTINEL")


def test_fake_client_fixture_failure_does_not_leak_exception_chain() -> None:
    with pytest.raises(ProviderInvalidResult) as captured:
        FakeGitHubClient(
            repositories={"ESP32": FailingFixtureValues()},  # type: ignore[arg-type]
        )

    rendered = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert str(captured.value) == "GitHub client fixture is invalid"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "SECRET_SENTINEL" not in rendered
    assert "SECRET_SENTINEL" not in _exception_chain_text(captured.value)


def test_raw_models_are_not_exported_from_github_package_root() -> None:
    for package in (github_package, providers_package, knowledge_package):
        for name in (
            "GitHubRepositoryItem",
            "GitHubCodeItem",
            "GitHubIssueItem",
            "GitHubReleaseItem",
        ):
            assert not hasattr(package, name)
